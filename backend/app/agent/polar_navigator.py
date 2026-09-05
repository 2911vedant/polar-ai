"""
POLAR-AI Polar Navigator
AI assistant that answers navigation questions using real application data.

Priority:
1. If LLM key available → use LLM with tool-calling
2. Otherwise → deterministic rule-based assistant
"""
import re
import json
from datetime import datetime, timezone
from typing import Dict, Any
from app.config import settings
from app.agent.tools import TOOLS
from loguru import logger


class PolarNavigator:
    """
    Polar Navigator AI assistant.
    Uses real application data via tool calls to answer questions.
    Falls back to deterministic rule-based reasoning when no LLM is available.
    """

    def __init__(self):
        self.use_llm = settings.has_llm
        self.provider = settings.llm_provider
        logger.info(f"PolarNavigator initialized. LLM: {self.provider}")

    async def query(self, question: str, context: Dict = {}) -> Dict:
        """Process a navigation question."""
        if self.use_llm:
            try:
                return await self._llm_query(question, context)
            except Exception as e:
                logger.warning(f"LLM query failed ({e}), falling back to rule-based")

        return self._rule_based_query(question, context)

    async def _llm_query(self, question: str, context: Dict) -> Dict:
        """LLM-powered query with tool calling."""
        # Gather relevant data via tools
        tools_used = []
        tool_results = {}

        # Always fetch dashboard and vessel status
        vessel = TOOLS["get_vessel_status"]()
        tool_results["vessel_status"] = vessel
        tools_used.append("get_vessel_status")

        question_lower = question.lower()

        if any(k in question_lower for k in ["ice", "concentration", "sea ice"]):
            tool_results["ice_conditions"] = TOOLS["get_current_ice_conditions"]()
            tool_results["ice_forecast"] = TOOLS["get_sea_ice_forecast"](72)
            tools_used.extend(["get_current_ice_conditions", "get_sea_ice_forecast"])

        if any(k in question_lower for k in ["iceberg", "berg", "trajectory"]):
            icebergs = TOOLS["get_icebergs"]()
            tool_results["icebergs"] = icebergs
            tools_used.append("get_icebergs")
            # Get trajectory of highest risk iceberg
            high_risk = next(
                (ib for ib in icebergs.get("icebergs", []) if ib.get("risk_level") == "high"),
                None
            )
            if high_risk:
                traj = TOOLS["get_iceberg_trajectory"](high_risk["iceberg_name"])
                tool_results["iceberg_trajectory"] = traj
                tools_used.append("get_iceberg_trajectory")

        if any(k in question_lower for k in ["route", "path", "navigate", "safest", "shortest"]):
            routes = TOOLS["compare_routes"](vessel["latitude"], vessel["longitude"], -67.57, -68.13)
            tool_results["routes"] = routes
            tools_used.append("compare_routes")

        if any(k in question_lower for k in ["weather", "wind", "storm"]):
            tool_results["weather"] = TOOLS["get_weather"]()
            tools_used.append("get_weather")

        if any(k in question_lower for k in ["risk", "danger", "safe", "hazard"]):
            tool_results["risk"] = TOOLS["calculate_navigation_risk"](
                vessel["latitude"], vessel["longitude"]
            )
            tools_used.append("calculate_navigation_risk")

        # Build context for LLM
        data_context = json.dumps(tool_results, indent=2, default=str)[:3000]

        system_prompt = """You are Polar Navigator, the AI assistant for POLAR-AI, 
an Antarctic navigation decision support system. You have access to real-time 
sea-ice data, iceberg tracking, weather conditions, and route planning algorithms.

Answer navigation questions using ONLY the data provided. Be specific and cite numbers.
Always mention if data is from demo/simulation mode.
Add the scientific disclaimer when giving safety-critical advice.

Keep responses concise but complete (3-5 sentences for most questions).
"""
        user_prompt = f"""Navigation question: {question}

Current application data:
{data_context}

Answer based on the above data only."""

        if self.provider == "openai":
            response = await self._call_openai(system_prompt, user_prompt)
        elif self.provider == "gemini":
            response = await self._call_gemini(system_prompt, user_prompt)
        elif self.provider == "groq":
            response = await self._call_groq(system_prompt, user_prompt)
        else:
            response = self._rule_based_query(question, context)["response"]

        return {
            "question": question,
            "response": response,
            "tools_used": tools_used,
            "data_mode": "demo",
            "llm_provider": self.provider,
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }

    async def _call_openai(self, system: str, user: str) -> str:
        from openai import AsyncOpenAI
        client = AsyncOpenAI(api_key=settings.OPENAI_API_KEY)
        completion = await client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[
                {"role": "system", "content": system},
                {"role": "user", "content": user},
            ],
            max_tokens=500,
            temperature=0.3,
        )
        return completion.choices[0].message.content

    async def _call_gemini(self, system: str, user: str) -> str:
        import google.generativeai as genai
        genai.configure(api_key=settings.GEMINI_API_KEY)
        model = genai.GenerativeModel("gemini-1.5-flash")
        result = model.generate_content(f"{system}\n\n{user}")
        return result.text

    async def _call_groq(self, system: str, user: str) -> str:
        from groq import AsyncGroq
        client = AsyncGroq(api_key=settings.GROQ_API_KEY)
        completion = await client.chat.completions.create(
            model="llama-3.1-8b-instant",
            messages=[
                {"role": "system", "content": system},
                {"role": "user", "content": user},
            ],
            max_tokens=500,
            temperature=0.3,
        )
        return completion.choices[0].message.content

    def _rule_based_query(self, question: str, context: Dict) -> Dict:
        """
        Deterministic rule-based navigator.
        Inspects actual data from tools and generates structured responses.
        """
        q = question.lower()
        tools_used = []
        response_parts = []

        # Always fetch core data
        vessel = TOOLS["get_vessel_status"]()
        tools_used.append("get_vessel_status")

        # ── Route questions ────────────────────────────────────────────────────
        if any(k in q for k in ["route", "path", "safest route", "which route", "should take"]):
            routes_data = TOOLS["compare_routes"](
                vessel["latitude"], vessel["longitude"], -67.57, -68.13
            )
            tools_used.append("compare_routes")

            routes = routes_data.get("routes", [])
            if routes:
                sorted_by_risk = sorted(routes, key=lambda r: r["overall_risk_score"])
                safest = sorted_by_risk[0]
                shortest = min(routes, key=lambda r: r["total_distance_km"])
                most_fuel_eff = min(routes, key=lambda r: r["estimated_fuel_tonnes"])

                response_parts.append(
                    f"Based on current conditions, **{safest['route_type'].replace('_', ' ').title()} route** "
                    f"is recommended with the lowest risk score: {safest['overall_risk_score']*100:.0f}/100 "
                    f"(category: {safest['risk_category'].upper()})."
                )
                response_parts.append(
                    f"It covers {safest['total_distance_km']:.0f} km in approximately "
                    f"{safest['estimated_duration_hours']:.0f} hours, consuming "
                    f"~{safest['estimated_fuel_tonnes']:.0f} tonnes of fuel."
                )
                if safest["iceberg_intersections"] > 0:
                    response_parts.append(
                        f"⚠️ Note: {safest['iceberg_intersections']} potential iceberg zone(s) detected along route. "
                        f"Post additional lookouts."
                    )
                else:
                    response_parts.append(
                        f"No iceberg trajectory intersections detected. Average ice concentration: "
                        f"{safest['avg_ice_concentration']*100:.0f}%."
                    )
                if shortest != safest:
                    dist_diff = safest["total_distance_km"] - shortest["total_distance_km"]
                    response_parts.append(
                        f"The shortest route saves {dist_diff:.0f} km but has a higher risk score of "
                        f"{shortest['overall_risk_score']*100:.0f}/100."
                    )

        # ── Why is route dangerous ─────────────────────────────────────────────
        elif any(k in q for k in ["why", "dangerous", "risk", "hazard"]):
            risk_data = TOOLS["calculate_navigation_risk"](vessel["latitude"], vessel["longitude"])
            tools_used.append("calculate_navigation_risk")

            response_parts.append(
                f"Navigation risk at current vessel position is "
                f"**{risk_data['total_risk_score']*100:.0f}/100** ({risk_data['risk_category'].upper()})."
            )
            response_parts.append("**Major contributing factors:**")
            for factor in risk_data["risk_factors"][:4]:
                response_parts.append(f"• {factor['text']}")
            for rec in risk_data["recommendations"][:2]:
                response_parts.append(f"→ {rec}")

        # ── Iceberg questions ──────────────────────────────────────────────────
        elif any(k in q for k in ["iceberg", "berg", "ice mass"]):
            icebergs = TOOLS["get_icebergs"]()
            tools_used.append("get_icebergs")

            total = icebergs["total_count"]
            high_risk = icebergs["high_risk_count"]
            response_parts.append(
                f"Currently tracking **{total} icebergs** in the Antarctic region. "
                f"{high_risk} are classified as high-risk."
            )

            high_risk_list = [ib for ib in icebergs["icebergs"] if ib["risk_level"] == "high"]
            if high_risk_list:
                for ib in high_risk_list[:3]:
                    traj = TOOLS["get_iceberg_trajectory"](ib["iceberg_name"])
                    tools_used.append("get_iceberg_trajectory")
                    ca = traj.get("closest_approach_km")
                    ca_str = f"Closest approach to vessel: {ca:.0f} km." if ca else ""
                    response_parts.append(
                        f"• **{ib['iceberg_name']}**: {ib['length_km']:.0f} × {ib['width_km']:.0f} km, "
                        f"drifting at {ib['drift_speed_kmh']:.2f} km/h. {ca_str}"
                    )

        # ── Sea ice questions ──────────────────────────────────────────────────
        elif any(k in q for k in ["sea ice", "ice concentration", "ice coverage", "sic"]):
            ice = TOOLS["get_current_ice_conditions"]()
            forecast = TOOLS["get_sea_ice_forecast"](72)
            tools_used.extend(["get_current_ice_conditions", "get_sea_ice_forecast"])

            response_parts.append(
                f"Current Antarctic sea-ice coverage: **{ice['coverage_pct']:.1f}%** of the monitored region."
            )
            response_parts.append(
                f"At vessel position ({ice['location']['lat']:.1f}°, {ice['location']['lon']:.1f}°): "
                f"SIC = {ice['sea_ice_concentration']*100:.0f}% ({ice['ice_category'].replace('_', ' ')})."
            )
            if forecast:
                response_parts.append(
                    f"72-hour forecast model confidence: {forecast.get('overall_confidence', 0.7)*100:.0f}%. "
                    f"Expected MAE: {forecast.get('mae', 0.09):.3f}. "
                    f"The sea-ice pattern is expected to remain stable over the next 3 days."
                )

        # ── Weather questions ──────────────────────────────────────────────────
        elif any(k in q for k in ["weather", "wind", "temperature", "storm", "conditions"]):
            wx = TOOLS["get_weather"]()
            tools_used.append("get_weather")

            beaufort = "Light" if wx["wind_speed_ms"] < 8 else "Moderate" if wx["wind_speed_ms"] < 12 else "Strong"
            response_parts.append(
                f"Current conditions at vessel position: "
                f"Wind **{wx['wind_speed_ms']:.1f} m/s** from {wx['wind_direction_deg']:.0f}° ({beaufort}). "
                f"Temperature: {wx['air_temp_celsius']:.1f}°C."
            )
            risk_desc = "LOW" if wx["weather_risk_score"] < 0.3 else "MODERATE" if wx["weather_risk_score"] < 0.6 else "HIGH"
            response_parts.append(f"Weather risk contribution: {risk_desc} ({wx['weather_risk_score']*100:.0f}/100).")

        # ── Vessel questions ───────────────────────────────────────────────────
        elif any(k in q for k in ["vessel", "ship", "position", "status", "speed", "where is"]):
            response_parts.append(
                f"Vessel **{vessel.get('vessel_name', 'RV Polar Explorer')}** is currently at "
                f"{vessel['latitude']:.2f}°S, {vessel['longitude']:.2f}°E "
                f"(Status: {vessel['status'].title()})."
            )
            response_parts.append(
                f"Speed: {vessel['speed_knots']:.1f} knots | Heading: {vessel['heading_deg']:.0f}°. "
                f"Current risk level at vessel position: {vessel['current_risk']:.0f}/100."
            )

        # ── Generic / fallback ─────────────────────────────────────────────────
        else:
            dashboard = TOOLS["get_vessel_status"]()
            risk = TOOLS["calculate_navigation_risk"](vessel["latitude"], vessel["longitude"])
            tools_used.extend(["get_vessel_status", "calculate_navigation_risk"])

            response_parts.append(
                "Here is a summary of current Antarctic navigation conditions:"
            )
            response_parts.append(
                f"• **Overall risk**: {risk['total_risk_score']*100:.0f}/100 ({risk['risk_category'].upper()})"
            )
            response_parts.append(
                f"• **Sea ice risk**: {risk['sea_ice_risk']*100:.0f}/100 | "
                f"**Iceberg risk**: {risk['iceberg_risk']*100:.0f}/100"
            )
            response_parts.append(
                f"• **Weather risk**: {risk['weather_risk']*100:.0f}/100 | "
                f"**Ocean risk**: {risk['ocean_risk']*100:.0f}/100"
            )
            response_parts.append(
                "Ask me about: routes, icebergs, sea ice forecast, weather, "
                "vessel status, or risk assessment."
            )

        # Disclaimer for safety questions
        if any(k in q for k in ["route", "safe", "navigate", "proceed", "should"]):
            response_parts.append(
                "\n> ⚠️ *POLAR-AI is a research prototype. All data is SIMULATION/DEMO. "
                "Do not use for real navigation decisions.*"
            )

        response = "\n\n".join(response_parts) if response_parts else (
            "I'm sorry, I couldn't find relevant data for that query. "
            "Try asking about sea ice, icebergs, routes, weather, or vessel status."
        )

        return {
            "question": question,
            "response": response,
            "tools_used": tools_used,
            "data_mode": "demo",
            "llm_provider": "rule_based",
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }
