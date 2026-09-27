import hashlib
from dataclasses import dataclass
from pathlib import Path

from PIL import Image
from sqlalchemy.ext.asyncio import AsyncSession

from geodom_backend.db.models import ApartmentPhoto
from geodom_backend.db.repositories import ApartmentPhotoRepository, ApartmentRepository
from geodom_backend.storage.provider import ObjectStorage


@dataclass
class MediaImportReport:
    apartments: int = 0
    imported: int = 0
    existing: int = 0
    unmatched: int = 0
    publication_enabled: int = 0


class HousingMediaImportService:
    """Import media/apartments/<source>/<source_id>/ without guessing listing IDs.

    Object keys are stable, and existing rows/cover choices survive reruns.
    Files remain private unless the operator explicitly authorizes publication.
    """

    def __init__(self, session: AsyncSession, storage: ObjectStorage):
        self._session = session
        self._storage = storage
        self._apartments = ApartmentRepository(session)
        self._photos = ApartmentPhotoRepository(session)

    async def import_directory(
        self, root: Path, *, bucket: str, allow_publication: bool = False
    ) -> MediaImportReport:
        root = root.resolve()
        directory = root / "apartments"
        if not directory.is_dir():
            raise ValueError(f"Missing directory: {directory}")
        report = MediaImportReport()
        for folder in sorted(directory.glob("*/*")):
            if not folder.is_dir():
                continue
            files = sorted(p for p in folder.iterdir() if p.suffix.lower() in {".webp", ".jpg", ".jpeg", ".png"})
            if not files:
                continue
            apartment = await self._apartments.get_by_source(source=folder.parent.name, source_id=folder.name)
            if apartment is None:
                report.unmatched += len(files)
                continue
            # Never attach imported archive photos to a user-owned listing.
            if apartment.owner_id is not None or apartment.origin.value != "seed":
                raise ValueError(f"Not a seed apartment: {apartment.id}")
            try:
                photos = await self._photos.get_all(apartment.id)
                existing = {(photo.bucket, photo.storage_key): photo for photo in photos}
                position = max((photo.position for photo in photos), default=-1) + 1
                has_cover = any(photo.is_cover for photo in photos)
                for path in files:
                    if not path.resolve().is_relative_to(root):
                        raise ValueError(f"Media escapes root: {path}")
                    key = path.relative_to(root).as_posix()
                    photo = existing.get((bucket, key))
                    if photo is not None:
                        report.existing += 1
                        if allow_publication and not photo.publication_allowed:
                            photo.publication_allowed = True
                            photo.rights_status = "operator_authorized_for_publication"
                            report.publication_enabled += 1
                        continue
                    data = path.read_bytes()
                    digest = hashlib.sha256(data).hexdigest()
                    # Archive filenames are content hashes. Catch damaged/misplaced files.
                    if len(path.stem) == 64 and path.stem.lower() != digest:
                        raise ValueError(f"SHA-256 mismatch: {path}")
                    with Image.open(path) as image:
                        width, height = image.size
                        mime_type = Image.MIME[image.format]
                        image.verify()
                    await self._storage.upload(bucket=bucket, key=key, data=data, content_type=mime_type)
                    photo = ApartmentPhoto(
                        apartment_id=apartment.id, external_id=f"local-media:{key}",
                        bucket=bucket, storage_key=key, local_path=f"media/{key}",
                        source=apartment.source, listing_url=apartment.source_url,
                        position=position, is_cover=not has_cover, width=width, height=height,
                        mime_type=mime_type, size_bytes=len(data), sha256=digest,
                        rights_status="operator_authorized_for_publication" if allow_publication else "not_verified_for_republication",
                        attribution="СИБДОМ" if apartment.source == "sibdom" else apartment.source,
                        publication_allowed=allow_publication, image_kind="photo",
                    )
                    await self._photos.add_imported(photo)
                    report.imported += 1
                    report.publication_enabled += int(allow_publication)
                    position += 1
                    has_cover = True
                await self._session.commit()
            except Exception:
                await self._session.rollback()
                # Stable storage keys make uploaded objects reusable on retry.
                raise
            report.apartments += 1
            if report.apartments % 25 == 0:
                print(f"Apartments: {report.apartments}; imported: {report.imported}; existing: {report.existing}", flush=True)
        return report
