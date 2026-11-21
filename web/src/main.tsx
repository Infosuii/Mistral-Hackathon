import { createRoot } from 'react-dom/client'
import '@fontsource/barlow/400.css'
import '@fontsource/barlow/600.css'
import '@fontsource/barlow-condensed/600.css'
import '@fontsource/barlow-condensed/700.css'
import { App } from './App'
import { exampleState } from './state'
import './screen.css'

createRoot(document.getElementById('root')!).render(<App state={exampleState} />)
