from __future__ import annotations

import datetime
import re
from typing import Any, Dict, List, Optional


class SafetyChatbot:
    """
    IronEye Local Workplace Safety Assistant.

    Provides instant guidance on workplace safety regulations, PPE, fire procedures,
    and live dashboard telemetry without external API dependencies.
    """

    SAFETY_KNOWLEDGE = [
        {
            "keywords": ["fire", "flame", "burn", "extinguisher", "combustible"],
            "topic": "Fire Safety & Extinguisher Guidelines",
            "response": (
                "🔥 **Fire Safety Protocol**:\n"
                "- **Class A (Wood/Paper)**: Water, Foam, Dry Chemical.\n"
                "- **Class B (Flammable Liquids)**: CO2, Dry Chemical.\n"
                "- **Class C (Electrical)**: CO2, Dry Chemical. *Never use water on electrical fires!*\n\n"
                "**PASS Technique**: **P**ull the pin, **A**im at base of fire, **S**queeze trigger, **S**weep side-to-side.\n"
                "If fire is uncontained, trigger manual alarm and evacuate immediately."
            ),
        },
        {
            "keywords": ["smoke", "haze", "fumes", "inhalation", "ventilation"],
            "topic": "Smoke Hazard & Evacuation",
            "response": (
                "💨 **Smoke Hazard Response**:\n"
                "- Stay low to the ground where air is cooler and cleaner.\n"
                "- Cover mouth and nose with a damp cloth if available.\n"
                "- Feel doors for heat with the back of your hand before opening.\n"
                "- Proceed calmly to the nearest marked Emergency Exit."
            ),
        },
        {
            "keywords": ["ppe", "helmet", "goggles", "gloves", "boots", "vest", "protective equipment"],
            "topic": "Personal Protective Equipment (PPE)",
            "response": (
                "🛈 **Required Workplace PPE Standard**:\n"
                "- **Head Protection**: Hard hat (ANSI Z89.1) required in overhead hazard zones.\n"
                "- **Eye Protection**: Safety glasses/goggles (ANSI Z87.1).\n"
                "- **High-Visibility**: Class 2 or 3 high-vis vest in vehicle/equipment areas.\n"
                "- **Footwear**: Steel-toe safety boots with non-slip soles.\n"
                "- **Hearing**: Earplugs or earmuffs when noise exceeds 85 dBA."
            ),
        },
        {
            "keywords": ["zone", "safety zone", "boundary", "intruder", "restricted", "polygon"],
            "topic": "Safety Zone Configuration",
            "response": (
                "📐 **Safety Zone System**:\n"
                "- IronEye uses ground-contact foot positioning (`feet_x = (x1+x2)/2`, `feet_y = y2`) to eliminate false alarms from gesturing arms.\n"
                "- Click '✏ Draw Zone' on the dashboard, click points on the feed, and double-click to save.\n"
                "- Detections inside the zone require 10 consecutive frames (~330ms) before escalating to CRITICAL alert."
            ),
        },
        {
            "keywords": ["risk", "level", "critical", "high", "low", "threshold", "confirmation"],
            "topic": "Risk Level Definitions",
            "response": (
                "📊 **IronEye Risk Classifications**:\n"
                "- **LOW (Green)**: Objects detected outside safety zone or normal baseline.\n"
                "- **HIGH (Amber)**: Monitored hazard detected inside zone, pending temporal confirmation (< 10 frames).\n"
                "- **CRITICAL (Red)**: Monitored hazard confirmed inside safety zone for 10+ consecutive frames (~330ms). Triggers audible alarm and optional SMS."
            ),
        },
        {
            "keywords": ["evacuation", "emergency", "exit", "assembly", "muster"],
            "topic": "Emergency Evacuation Plan",
            "response": (
                "🚪 **Emergency Evacuation Procedure**:\n"
                "1. Stop work immediately and secure high-hazard machinery.\n"
                "2. Follow illuminated EXIT signage to designated assembly point.\n"
                "3. Do NOT use elevators during fire or structural emergencies.\n"
                "4. Report to your safety warden for headcount at the assembly area."
            ),
        },
        {
            "keywords": ["phone", "camera", "cctv", "mobile", "android", "stream"],
            "topic": "Phone Camera Setup",
            "response": (
                "📱 **Phone Camera Integration**:\n"
                "1. Connect phone and laptop to the same Wi-Fi network.\n"
                "2. Open `https://<LAPTOP-IP>:8000/phone` on your phone browser.\n"
                "3. Tap **Start Streaming** and grant camera permissions.\n"
                "4. Click **Switch to Phone Camera** on the dashboard."
            ),
        },
        {
            "keywords": ["alarm", "audio", "sound", "silence", "mute"],
            "topic": "Audible Alarm Controls",
            "response": (
                "🔔 **Audible Alarm Operations**:\n"
                "- Browser autoplay policy requires a one-time click on the dashboard to enable audio.\n"
                "- Click **🔕 Silence Alarm** to mute active sirens. The alarm automatically re-arms for subsequent incidents when risk drops back below CRITICAL."
            ),
        },
    ]

    def answer_query(self, message: str, stream_manager: Optional[Any] = None) -> Dict[str, Any]:
        """Process user message and generate contextual response."""
        text = message.lower().strip()

        # Handle empty/short input
        if not text:
            return {
                "reply": "Hello! I am the IronEye Workplace Safety Assistant. How can I help you today with safety procedures, PPE, or system status?",
                "topic": "Greeting",
                "confidence": 1.0,
            }

        # Check for live system status query
        if any(w in text for w in ["status", "live", "current risk", "how many incidents", "camera active", "model"]):
            if stream_manager:
                status = stream_manager.get_status()
                incidents = stream_manager.get_recent_incidents()
                latest_risk = getattr(stream_manager, "latest_frame_risk", None)
                overall = getattr(latest_risk, "overall_risk", "LOW") if latest_risk else "LOW"

                reply = (
                    f"📡 **Live System Status**:\n"
                    f"- **Monitoring State**: {status.get('status', 'UNKNOWN')}\n"
                    f"- **Current Risk Level**: {overall}\n"
                    f"- **Video Source**: {status.get('video_source', 'N/A')}\n"
                    f"- **Processing Speed**: {status.get('fps', 0.0)} FPS\n"
                    f"- **Active Detections**: {status.get('detection_count', 0)} objects\n"
                    f"- **Recent Incidents Recorded**: {len(incidents)} total\n"
                )
                if status.get("use_phone_camera"):
                    reply += f"- **Mode**: Phone Camera ({status.get('phone_camera_id', 'mobile')})\n"

                return {
                    "reply": reply,
                    "topic": "Live System Status",
                    "confidence": 0.95,
                }

        # Keyword matching against safety knowledge base
        best_match = None
        best_score = 0

        for item in self.SAFETY_KNOWLEDGE:
            score = sum(1 for kw in item["keywords"] if kw in text)
            if score > best_score:
                best_score = score
                best_match = item

        if best_match and best_score > 0:
            return {
                "reply": best_match["response"],
                "topic": best_match["topic"],
                "confidence": min(1.0, 0.6 + (best_score * 0.2)),
            }

        # General safety fallback response
        return {
            "reply": (
                "I am the **IronEye Safety Assistant**. I can help you with:\n"
                "- 🛈 Workplace PPE requirements & standards\n"
                "- 🔥 Fire safety & extinguisher procedures\n"
                "- 🚪 Emergency evacuation protocols\n"
                "- 📐 Safety zone configuration & risk engine thresholds\n"
                "- 📡 Live telemetry and status queries\n\n"
                "*Note: For immediate life-safety emergencies, trigger the physical alarm and call emergency services (911/112).* "
                "Please rephrase your question or select one of the topics above."
            ),
            "topic": "General Help",
            "confidence": 0.4,
        }
