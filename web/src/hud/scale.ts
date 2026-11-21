import { createContext, useContext } from 'react'
import atlas from '../atlas.json'

/** The generated world is this many times larger than the authored 1740×1060 outline. */
export const WORLD = atlas.scale

/** Authored offsets (ship berths, labels) in generated-world units. */
export const world = (value: number) => value * WORLD

/**
 * Markers, labels, leaders and national borders keep a steady on-screen size while the
 * camera zooms over a much larger world; buildings, roads and fields are world-sized.
 */
export const markerScaleFor = (zoom: number) => Math.min(8, Math.max(.32, .82 / zoom))
export const MarkerScale = createContext(1)
export const useMarkerScale = () => useContext(MarkerScale)
