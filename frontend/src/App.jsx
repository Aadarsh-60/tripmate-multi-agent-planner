import React, { useState, useEffect, useRef } from 'react'
import { Zap, CheckCircle, Loader, CloudSun, DollarSign, MapPin, Plane, Hotel, User, FileText, Globe, Settings, Cpu } from 'lucide-react'
import { MapContainer, TileLayer, Marker, Popup } from 'react-leaflet'
import 'leaflet/dist/leaflet.css'
import L from 'leaflet'

// Fix Leaflet default marker icon issue in React
delete L.Icon.Default.prototype._getIconUrl
L.Icon.Default.mergeOptions({
  iconRetinaUrl: 'https://cdnjs.cloudflare.com/ajax/libs/leaflet/1.9.4/images/marker-icon-2x.png',
  iconUrl: 'https://cdnjs.cloudflare.com/ajax/libs/leaflet/1.9.4/images/marker-icon.png',
  shadowUrl: 'https://cdnjs.cloudflare.com/ajax/libs/leaflet/1.9.4/images/marker-shadow.png',
})

const AGENTS = [
  { id: 'profile_agent', num: '01', title: 'Profile Engine', desc: 'Extracting preferences & destination', icon: User },
  { id: 'flight_agent', num: '02', title: 'Flight Search', desc: 'Finding live routes & schedules', icon: Plane },
  { id: 'hotel_agent', num: '03', title: 'Accommodation', desc: 'Scouting best hotels', icon: Hotel },
  { id: 'weather_agent', num: '04', title: 'Weather Forecast', desc: 'Checking local climate', icon: CloudSun },
  { id: 'currency_agent', num: '05', title: 'Currency Exchange', desc: 'Fetching live rates', icon: DollarSign },
  { id: 'map_agent', num: '06', title: 'Local Attractions', desc: 'Mapping tourist spots', icon: MapPin },
  { id: 'final_agent', num: '07', title: 'Itinerary Planner', desc: 'Structuring the final plan', icon: FileText },
]

const MODELS = [
  { id: 'groq', name: 'Groq (Llama 3)', icon: '⚡' },
  { id: 'openai', name: 'OpenAI (GPT-4o)', icon: '🧠' },
  { id: 'gemini', name: 'Google Gemini', icon: '💎' },
]

const LANGUAGES = [
  { id: 'English', name: 'English', flag: '🇬🇧' },
  { id: 'Hindi', name: 'हिंदी', flag: '🇮🇳' },
  { id: 'Spanish', name: 'Español', flag: '🇪🇸' },
  { id: 'French', name: 'Français', flag: '🇫🇷' },
  { id: 'Japanese', name: '日本語', flag: '🇯🇵' },
  { id: 'German', name: 'Deutsch', flag: '🇩🇪' },
  { id: 'Arabic', name: 'العربية', flag: '🇸🇦' },
]

function App() {
  const [prompt, setPrompt] = useState('')
  const [loading, setLoading] = useState(false)
  const [activeNode, setActiveNode] = useState(null)
  const [completedNodes, setCompletedNodes] = useState([])
  const [error, setError] = useState(null)
  
  const [selectedModel, setSelectedModel] = useState('groq')
  const [selectedLanguage, setSelectedLanguage] = useState('English')
  
  const [hitlDraft, setHitlDraft] = useState(null)
  const [threadId, setThreadId] = useState(null)
  const [finalPlan, setFinalPlan] = useState(null)
  const [planMeta, setPlanMeta] = useState(null) // destination, image, coords
  const [feedback, setFeedback] = useState('')
  const [showPlan, setShowPlan] = useState(false)

  const handleSSE = async (response) => {
    const reader = response.body.getReader()
    const decoder = new TextDecoder()
    let buffer = ''

    while (true) {
      const { value, done } = await reader.read()
      if (done) break
      
      buffer += decoder.decode(value, { stream: true })
      const parts = buffer.split('\n\n')
      buffer = parts.pop() || ''
      
      for (let part of parts) {
        const trimmed = part.trim()
        if (trimmed.startsWith('data: ')) {
          try {
            const jsonStr = trimmed.substring(6)
            const data = JSON.parse(jsonStr)
            
            if (data.type === 'progress') {
              setActiveNode(data.node)
              setCompletedNodes(prev => {
                if (!prev.includes(data.node)) return [...prev, data.node]
                return prev
              })
            } else if (data.type === 'hitl_wait') {
              setHitlDraft(data.draft)
              setThreadId(data.thread_id)
              setPlanMeta({
                destination: data.draft.destination,
                image: data.draft.destination_image,
                lat: data.draft.destination_lat,
                lon: data.draft.destination_lon,
              })
              setActiveNode(null)
              setLoading(false)
              return
            } else if (data.type === 'final_plan') {
              setFinalPlan(data.plan)
              if (data.meta) {
                setPlanMeta({
                  destination: data.meta.destination,
                  image: data.meta.destination_image,
                  lat: data.meta.destination_lat,
                  lon: data.meta.destination_lon,
                })
              }
              setActiveNode(null)
              setShowPlan(true)
            } else if (data.type === 'error') {
              setError(data.error)
              setLoading(false)
            }
          } catch (parseErr) {
            console.warn('SSE parse error:', parseErr)
          }
        }
      }
    }
    setLoading(false)
  }

  const handleSubmit = async (e) => {
    e.preventDefault()
    if (!prompt.trim()) return
    
    setLoading(true)
    setError(null)
    setFinalPlan(null)
    setHitlDraft(null)
    setCompletedNodes([])
    setActiveNode(null)
    setShowPlan(false)
    setPlanMeta(null)

    try {
      const response = await fetch('/api/travel', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ 
          message: prompt, 
          thread_id: null,
          model: selectedModel,
          language: selectedLanguage 
        })
      })
      await handleSSE(response)
    } catch (err) {
      setError(err.message)
      setLoading(false)
    }
  }

  const handleApprove = async () => {
    setLoading(true)
    setHitlDraft(null)
    
    try {
      const response = await fetch('/api/approve', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ thread_id: threadId, action: 'approve', feedback })
      })
      await handleSSE(response)
    } catch (err) {
      setError(err.message)
      setLoading(false)
    }
  }

  return (
    <div className="app-wrapper">
      {/* ===== TOP SECTION ===== */}
      <div className="top-section">
        <div className="left-panel">
          <div>
            <h1 className="hero-title">
              Intelligent travel planner,<br/>
              <span>multiple agents working together.</span>
            </h1>
            <p className="hero-subtitle">Flights • Hotels • Weather • Currency • Itinerary</p>
          </div>

          {/* Settings Bar: Model + Language */}
          <div className="settings-bar">
            <div className="setting-group">
              <label><Cpu size={14}/> AI Model</label>
              <select value={selectedModel} onChange={e => setSelectedModel(e.target.value)} disabled={loading}>
                {MODELS.map(m => (
                  <option key={m.id} value={m.id}>{m.icon} {m.name}</option>
                ))}
              </select>
            </div>
            <div className="setting-group">
              <label><Globe size={14}/> Language</label>
              <select value={selectedLanguage} onChange={e => setSelectedLanguage(e.target.value)} disabled={loading}>
                {LANGUAGES.map(l => (
                  <option key={l.id} value={l.id}>{l.flag} {l.name}</option>
                ))}
              </select>
            </div>
          </div>

          <form className="input-section" onSubmit={handleSubmit}>
            <label className="input-label">YOUR DESTINATION & REQUIREMENTS</label>
            <textarea 
              className="chat-input"
              value={prompt}
              onChange={e => setPrompt(e.target.value)}
              placeholder="e.g. Plan a 7 days Japan trip from Delhi under 2 Lakhs..."
              disabled={loading}
            />
            <button type="submit" className="submit-btn" disabled={loading || !!hitlDraft}>
              <Zap size={16} /> {loading ? 'AGENTS WORKING...' : 'GENERATE TRAVEL PLAN →'}
            </button>
          </form>

          {error && <div className="error-box">{error}</div>}
        </div>

        <div className="right-panel">
          {AGENTS.map(agent => {
            const isCompleted = completedNodes.includes(agent.id)
            const isActive = activeNode === agent.id
            const Icon = agent.icon
            
            return (
              <div key={agent.id} className={`progress-card ${isActive ? 'active' : ''} ${isCompleted ? 'completed' : ''}`}>
                <div className="step-icon-wrap">
                  {isActive ? <Loader size={20} className="spin" /> : isCompleted ? <CheckCircle size={20} className="check-icon" /> : <Icon size={20} />}
                </div>
                <div className="step-content">
                  <h3>{agent.num} &nbsp;{agent.title}</h3>
                  <p>{isActive ? 'Working...' : isCompleted ? 'Done ✓' : agent.desc}</p>
                </div>
              </div>
            )
          })}
        </div>
      </div>

      {/* ===== DESTINATION IMAGE BANNER ===== */}
      {planMeta && planMeta.image && (
        <div className="full-width-section">
          <div className="destination-banner">
            <img src={planMeta.image} alt={planMeta.destination} />
            <div className="destination-banner-overlay">
              <h2>{planMeta.destination}</h2>
            </div>
          </div>
        </div>
      )}

      {/* ===== INTERACTIVE MAP ===== */}
      {planMeta && planMeta.lat !== 0 && planMeta.lon !== 0 && (
        <div className="full-width-section">
          <div className="map-container">
            <h3><MapPin size={18}/> Interactive Map — {planMeta.destination}</h3>
            <MapContainer 
              center={[planMeta.lat, planMeta.lon]} 
              zoom={11} 
              style={{ height: '350px', width: '100%', borderRadius: '10px' }}
              key={`${planMeta.lat}-${planMeta.lon}`}
            >
              <TileLayer
                attribution='&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a>'
                url="https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png"
              />
              <Marker position={[planMeta.lat, planMeta.lon]}>
                <Popup>📍 {planMeta.destination}</Popup>
              </Marker>
            </MapContainer>
          </div>
        </div>
      )}

      {/* ===== HITL APPROVAL ===== */}
      {hitlDraft && (
        <div className="full-width-section">
          <div className="hitl-box">
            <h3>⏸ Human Review Required</h3>
            <p className="hitl-desc">
              All agents have finished collecting live data. Review below and provide any adjustments.
            </p>
            <div className="hitl-data-grid">
              <div className="hitl-data-card">
                <h4><Plane size={16}/> Flights</h4>
                <pre>{hitlDraft.flights || 'No data'}</pre>
              </div>
              <div className="hitl-data-card">
                <h4><Hotel size={16}/> Hotels</h4>
                <pre>{hitlDraft.hotels || 'No data'}</pre>
              </div>
              <div className="hitl-data-card">
                <h4><CloudSun size={16}/> Weather</h4>
                <pre>{hitlDraft.weather || 'No data'}</pre>
              </div>
              <div className="hitl-data-card">
                <h4><MapPin size={16}/> Places</h4>
                <pre>{hitlDraft.map || 'No data'}</pre>
              </div>
            </div>
            <textarea 
              className="hitl-feedback"
              value={feedback}
              onChange={e => setFeedback(e.target.value)}
              placeholder="Add feedback (e.g. I prefer 5 star hotels) or leave empty..."
            />
            <button className="approve-btn" onClick={handleApprove}>
              ✅ Approve & Generate Final Itinerary
            </button>
          </div>
        </div>
      )}

      {/* ===== FINAL PLAN ===== */}
      {finalPlan && showPlan && (
        <div className="full-width-section">
          <div className="result-area">
            <h2>🗺 Your AI Travel Plan</h2>

            <div className="summary-grid">
              <div className="summary-card">
                <div className="summary-card-icon"><DollarSign size={24}/></div>
                <div>
                  <h4>Estimated Budget</h4>
                  <p>{finalPlan.estimated_budget || 'N/A'}</p>
                </div>
              </div>
              <div className="summary-card">
                <div className="summary-card-icon"><CloudSun size={24}/></div>
                <div>
                  <h4>Weather Expected</h4>
                  <p>{finalPlan.weather_info || 'N/A'}</p>
                </div>
              </div>
              <div className="summary-card">
                <div className="summary-card-icon"><DollarSign size={24}/></div>
                <div>
                  <h4>Currency Info</h4>
                  <p>{finalPlan.exchange_rates || 'N/A'}</p>
                </div>
              </div>
            </div>

            <div className="plan-section">
              <h3>Trip Summary</h3>
              <p className="summary-text">{finalPlan.trip_summary || 'No summary.'}</p>
            </div>

            {finalPlan.flights && finalPlan.flights.length > 0 && (
              <div className="plan-section">
                <h3>✈ Flights</h3>
                <div className="flight-grid">
                  {finalPlan.flights.map((f, i) => (
                    <div key={i} className="flight-card">
                      <div className="flight-airline">{f.airline}</div>
                      <div className="flight-number">{f.flight_number}</div>
                      <div className="flight-route">{f.departure} → {f.arrival}</div>
                      <div className="flight-status">{f.status}</div>
                    </div>
                  ))}
                </div>
              </div>
            )}

            {finalPlan.hotels_and_places && finalPlan.hotels_and_places.length > 0 && (
              <div className="plan-section">
                <h3>🏨 Hotels & Places</h3>
                <ul className="places-list">
                  {finalPlan.hotels_and_places.map((p, i) => (
                    <li key={i}>{p}</li>
                  ))}
                </ul>
              </div>
            )}

            {finalPlan.itinerary && finalPlan.itinerary.length > 0 && (
              <div className="plan-section">
                <h3>📅 Day by Day Itinerary</h3>
                <div className="itinerary-grid">
                  {finalPlan.itinerary.map(day => (
                    <div key={day.day} className="day-card">
                      <div className="day-badge">Day {day.day}</div>
                      <h4>{day.title}</h4>
                      <ul>
                        {day.activities.map((act, i) => <li key={i}>{act}</li>)}
                      </ul>
                    </div>
                  ))}
                </div>
              </div>
            )}
          </div>
        </div>
      )}
    </div>
  )
}

export default App
