# Frontend performance roadmap

GeoDom remains frontend-only in this repository. This document is the performance gate for the visual phase.

## Budgets

- keep the primary decision flow usable before optional visual code finishes loading;
- target 60 FPS for normal transitions on modern desktop hardware;
- never animate layout-heavy map DOM on every map frame;
- respect `prefers-reduced-motion`;
- cap WebGL pixel ratio and fully dispose Three.js resources;
- keep large map datasets behind zoom-level detail and viewport culling.

## Map

Current strategy:

- zoom 3–8: city overview only; apartments and POI are not rendered;
- zoom 9–10: district-level overview; apartments stay hidden;
- zoom 11–12: apartments are clustered;
- zoom 13+: price pins are rendered only for the current padded viewport;
- if more than 320 apartments are visible, the map falls back to clusters instead of creating hundreds of price DOM nodes;
- POI appear from zoom 12, are viewport-culling aware and capped at 1200 rendered objects;
- map viewport synchronization is debounced so React is not updated on every raw map movement event.

Later scale pass:

- move very large apartment datasets to Yandex ObjectManager or a client spatial index;
- profile 10k / 50k / 100k synthetic apartment fixtures;
- split map collections so apartment, district, POI and workplace updates do not rebuild unrelated layers;
- benchmark cluster creation and balloon payload size.

## React and state

- Zustand is the shared UI/domain state layer;
- prefer narrow selectors instead of subscribing whole pages to the whole store;
- memoize derived lists used by map/catalog;
- keep server/demo normalization outside render paths;
- use React Profiler before adding manual memoization.

## Motion

- Framer Motion is for route/section state transitions and layout continuity, not perpetual decoration;
- use transform/opacity for animated UI whenever possible;
- use `whileInView` with `once:true` for reveal choreography;
- pause/remove animations that are not visible;
- avoid blur/filter animation on large surfaces;
- do not animate Yandex marker positions with React;
- compare tray and recommendation reordering may use layout animation because the number of elements is bounded.

## Three.js

- lazy load it separately from the critical UI;
- hide it on small screens;
- skip it for reduced-motion users;
- cap DPR at 1.5;
- use low-power renderer preference;
- dispose geometry, material, renderer and animation frame on unmount;
- later pause rendering with IntersectionObserver when the hero is offscreen.

## Images and bundles

Later performance pass:

- responsive `srcset/sizes` for apartment photos;
- explicit image dimensions to reduce layout shift;
- lazy decode below the fold;
- bundle analysis in CI;
- route-level code splitting review;
- preload only critical fonts/assets;
- remove duplicate animation/runtime dependencies before release.

## Performance definition of done

Before calling the visual frontend final:

1. run Lighthouse desktop/mobile;
2. record React Profiler on catalog filtering and recommendation reranking;
3. profile map with large synthetic fixtures;
4. verify no continuous animation work when tabs/sections are hidden;
5. verify reduced-motion behavior;
6. inspect bundle chunks and remove accidental eager Three.js loading;
7. test low-end mobile interaction manually.
