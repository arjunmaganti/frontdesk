import os
import requests
import logging
from datetime import datetime
from zoneinfo import ZoneInfo
import src.config as config

logger = logging.getLogger(__name__)

def get_available_slots(date_str: str) -> list[dict]:
    """
    Fetches available slots for a specific date (YYYY-MM-DD).
    Returns a list of dicts: [{"utc": "2026-07-16T16:00:00.000Z", "local": "09:00 AM"}]
    """
    if not config.CAL_API_KEY or not config.CAL_EVENT_TYPE_ID:
        logger.error("Cal.com API key or Event Type ID is not configured.")
        return []

    # Format start and end in UTC
    start = f"{date_str}T00:00:00Z"
    end = f"{date_str}T23:59:59Z"
    
    url = "https://api.cal.com/v2/slots"
    headers = {
        "Authorization": f"Bearer {config.CAL_API_KEY}",
        "cal-api-version": "2024-09-04"
    }
    params = {
        "start": start,
        "end": end,
        "eventTypeId": int(config.CAL_EVENT_TYPE_ID)
    }

    try:
        response = requests.get(url, headers=headers, params=params, timeout=10)
        if response.status_code != 200:
            logger.error(f"Error fetching slots from Cal.com: {response.text}")
            return []
            
        res_json = response.json()
        if res_json.get("status") != "success":
            logger.error(f"Cal.com returned error status: {res_json}")
            return []

        slots_data = res_json.get("data", {})
        # slots_data is a dict where keys are dates, e.g., {"2026-07-16": [{"start": "..."}]}
        day_slots = slots_data.get(date_str, [])
        
        # Get business timezone
        tz_str = config.BUSINESS_TIMEZONE or "America/Los_Angeles"
        try:
            tz = ZoneInfo(tz_str)
        except Exception:
            tz = ZoneInfo("America/Los_Angeles")

        parsed_slots = []
        for slot in day_slots:
            utc_time_str = slot.get("start")
            if not utc_time_str:
                continue
            
            # Parse UTC time
            # Replace Z with +00:00 for python's fromisoformat
            clean_time_str = utc_time_str.replace("Z", "+00:00")
            try:
                utc_dt = datetime.fromisoformat(clean_time_str)
                # Convert to business local time
                local_dt = utc_dt.astimezone(tz)
                local_display = local_dt.strftime("%I:%M %p")
                parsed_slots.append({
                    "utc": utc_time_str,
                    "local": local_display
                })
            except Exception as e:
                logger.error(f"Error parsing slot timestamp {utc_time_str}: {e}")
                
        return parsed_slots

    except Exception as e:
        logger.error(f"Exceptions in get_available_slots: {e}")
        return []

def create_booking(start_time_utc: str, name: str, email: str) -> dict:
    """
    Creates a booking in Cal.com for the specified start time (UTC ISO format).
    """
    if not config.CAL_API_KEY or not config.CAL_EVENT_TYPE_ID:
        return {"status": "error", "message": "Cal.com is not configured."}

    url = "https://api.cal.com/v2/bookings"
    headers = {
        "Authorization": f"Bearer {config.CAL_API_KEY}",
        "cal-api-version": "2024-09-04",
        "Content-Type": "application/json"
    }
    payload = {
        "start": start_time_utc,
        "eventTypeId": int(config.CAL_EVENT_TYPE_ID),
        "attendee": {
            "name": name,
            "email": email,
            "timeZone": config.BUSINESS_TIMEZONE or "America/Los_Angeles"
        }
    }

    try:
        response = requests.post(url, headers=headers, json=payload, timeout=10)
        res_json = response.json()
        if response.status_code in [200, 201] and res_json.get("status") == "success":
            return {"status": "success", "data": res_json.get("data")}
        else:
            logger.error(f"Error creating booking: {response.text}")
            return {"status": "error", "message": res_json.get("error", {}).get("message", "Booking failed.")}
    except Exception as e:
        logger.error(f"Exception in create_booking: {e}")
        return {"status": "error", "message": str(e)}
