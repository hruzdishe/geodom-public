import { useEffect, useRef } from 'react'
import * as THREE from 'three'

export default function CitySignal() {
  const mountRef = useRef<HTMLDivElement>(null)

  useEffect(() => {
    const mount = mountRef.current
    if (!mount || window.matchMedia('(prefers-reduced-motion: reduce)').matches) return

    let frame = 0
    let disposed = false
    let visible = true
    let pageVisible = document.visibilityState !== 'hidden'
    let running = false
    const scene = new THREE.Scene()
    const camera = new THREE.PerspectiveCamera(36,1,0.1,100)
    camera.position.set(0,0,7)

    let renderer:THREE.WebGLRenderer
    try {
      renderer = new THREE.WebGLRenderer({ alpha:true,antialias:true,powerPreference:'low-power' })
    } catch {
      return
    }

    renderer.setClearColor(0x000000,0)
    renderer.setPixelRatio(Math.min(window.devicePixelRatio || 1,1.5))
    renderer.domElement.setAttribute('aria-hidden','true')
    mount.appendChild(renderer.domElement)

    const group = new THREE.Group()
    scene.add(group)

    const columns = 8
    const rows = 5
    const positions:number[] = []
    const linePositions:number[] = []

    for (let y=0;y<rows;y++) {
      for (let x=0;x<columns;x++) {
        const px = (x-(columns-1)/2)*0.62
        const py = (y-(rows-1)/2)*0.55
        const wave = Math.sin(x*0.9+y*0.72)*0.34
        positions.push(px,py,wave)

        if (x<columns-1) {
          const nx = (x+1-(columns-1)/2)*0.62
          const nz = Math.sin((x+1)*0.9+y*0.72)*0.34
          linePositions.push(px,py,wave,nx,py,nz)
        }
        if (y<rows-1) {
          const ny = (y+1-(rows-1)/2)*0.55
          const nz = Math.sin(x*0.9+(y+1)*0.72)*0.34
          linePositions.push(px,py,wave,px,ny,nz)
        }
      }
    }

    const pointGeometry = new THREE.BufferGeometry()
    pointGeometry.setAttribute('position',new THREE.Float32BufferAttribute(positions,3))
    const pointMaterial = new THREE.PointsMaterial({
      color:0x2d86f3,
      size:0.075,
      transparent:true,
      opacity:0.58,
      sizeAttenuation:true
    })
    const points = new THREE.Points(pointGeometry,pointMaterial)
    group.add(points)

    const lineGeometry = new THREE.BufferGeometry()
    lineGeometry.setAttribute('position',new THREE.Float32BufferAttribute(linePositions,3))
    const lineMaterial = new THREE.LineBasicMaterial({
      color:0x21ad77,
      transparent:true,
      opacity:0.17
    })
    const lines = new THREE.LineSegments(lineGeometry,lineMaterial)
    group.add(lines)

    group.rotation.x = -0.36
    group.rotation.z = -0.08

    const resize = () => {
      if (!mount.clientWidth || !mount.clientHeight) return
      const width = mount.clientWidth
      const height = mount.clientHeight
      renderer.setSize(width,height,false)
      camera.aspect = width/height
      camera.updateProjectionMatrix()
    }

    const observer = new ResizeObserver(resize)
    observer.observe(mount)
    resize()

    const startedAt = performance.now()
    const render = (now:number) => {
      if (disposed || !visible || !pageVisible) {
        running = false
        return
      }
      running = true
      const time = (now-startedAt)/1000
      group.rotation.z = -0.08+Math.sin(time*0.22)*0.025
      group.rotation.y = Math.sin(time*0.17)*0.08
      points.position.z = Math.sin(time*0.42)*0.035
      renderer.render(scene,camera)
      frame = requestAnimationFrame(render)
    }
    const ensureRunning = () => {
      if (disposed || running || !visible || !pageVisible) return
      frame = requestAnimationFrame(render)
    }
    const intersectionObserver = new IntersectionObserver(entries => {
      visible = entries.some(entry => entry.isIntersecting)
      if (!visible) {
        cancelAnimationFrame(frame)
        running = false
      } else {
        ensureRunning()
      }
    },{ rootMargin:'80px',threshold:.01 })
    intersectionObserver.observe(mount)

    const onVisibilityChange = () => {
      pageVisible = document.visibilityState !== 'hidden'
      if (!pageVisible) {
        cancelAnimationFrame(frame)
        running = false
      } else {
        ensureRunning()
      }
    }
    document.addEventListener('visibilitychange',onVisibilityChange)
    ensureRunning()

    return () => {
      disposed = true
      cancelAnimationFrame(frame)
      observer.disconnect()
      intersectionObserver.disconnect()
      document.removeEventListener('visibilitychange',onVisibilityChange)
      pointGeometry.dispose()
      pointMaterial.dispose()
      lineGeometry.dispose()
      lineMaterial.dispose()
      renderer.dispose()
      renderer.domElement.remove()
    }
  },[])

  return <div ref={mountRef} className="city-signal" aria-hidden="true"/>
}
