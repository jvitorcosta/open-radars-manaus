"""Camera spots marked with a watch's Lap button: a drive recorded as an activity (Garmin, synced to
Strava), Lap pressed at each camera. Each press ends a lap, so every lap but the last (which ends
at Stop) is a mark at its end_index in the GPS track; the direction is the bearing from the track
point at least BACK_M before it.

The input file is what /radar-laps saves from Strava (laps and streams):
  {"activity": 123, "name": "...", "start": "2026-11-05T18:00:00Z",
   "laps": [{"start_index": 0, "end_index": 57}, ...],
   "latlng": [[lat, lng], ...], "time": [s, ...]}
(`time` is optional: seconds from the start, for the card's text).
"""
import math

BACK_M = 15   # the bearing needs some track behind the press: GPS jitter over a few metres is noise


def _metres(a, b):
    ky, kx = 110574, 111320 * math.cos(math.radians(a[0]))
    return math.hypot((b[1] - a[1]) * kx, (b[0] - a[0]) * ky)


def heading_at(track, i, back_m=BACK_M):
    """Bearing (0 = north) of travel into track[i], from the last point at least back_m before it;
    None when the car hadn't moved that far yet."""
    for j in range(i - 1, -1, -1):
        if _metres(track[j], track[i]) >= back_m:
            a, b = track[j], track[i]
            kx = math.cos(math.radians(a[0]))
            return round(math.degrees(math.atan2((b[1] - a[1]) * kx, b[0] - a[0]))) % 360
    return None


def marks_from_laps(activity):
    """Review-map items (guesses to confirm) for an activity's Lap presses, in order."""
    track = activity.get("latlng") or []
    times = activity.get("time") or []
    laps = activity.get("laps") or []
    out = []
    for n, lap in enumerate(laps[:-1], start=1):     # the last lap ends at Stop, not at a press
        i = lap.get("end_index")
        if i is None or not 0 <= i < len(track):
            continue
        lat, lon = track[i]
        when = " at %d:%02d" % divmod(int(times[i]), 60) if i < len(times) else ""
        out.append({"kind": "speed", "lat": round(lat, 6), "lon": round(lon, 6), "heading": heading_at(track, i),
                    "limit": None, "label": "", "source": "car", "guess": True, "how": "car",
                    "address": "Lap %d%s of activity %s" % (n, when, activity.get("activity", "?"))})
    return out
