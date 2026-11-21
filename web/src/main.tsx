import { createRoot } from 'react-dom/client'
import '@fontsource/barlow/400.css'
import '@fontsource/barlow/600.css'
import '@fontsource/barlow-condensed/600.css'
import '@fontsource/barlow-condensed/700.css'
import { GameSession } from './GameSession'
import './screen.css'
import './hud/hud.css'

createRoot(document.getElementById('root')!).render(<GameSession />)
