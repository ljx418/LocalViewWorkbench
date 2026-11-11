#!/usr/bin/env python3
"""One-off authoring helper for the S3-PREP-C independent blind prelabel.

It merges the independently observed, visually verified notes (OBS below) with
the preview-file identity that was independently recomputed from the retained
preview tree (preview-map.json).  It performs no inference, no model call and
no access to the original testSource media.  It is a review-authoring helper,
not a product tool.

Run:  python3 -B reports/v0-s3/preparation-05/independent-01/raw/build-prelabels.py
"""
from __future__ import annotations

import hashlib
import json
import pathlib

HERE = pathlib.Path(__file__).resolve().parent
ROOT = HERE.parents[4]
OUT = HERE.parent / "prelabels.json"
MAP = HERE / "preview-map.json"

RUNTIME_REL = ".agent-governance/runtime/receipts/s3-preview-c01/run-01"
RUNTIME_ABS_REDACTED = (
    "<orca-workspace>/lvw-v1-d0-implement/LVW_Prompt_Service_MasterPack_v2.0.0"
    + "/" + RUNTIME_REL
)

# --- the independently observed notes -------------------------------------
# Each entry was written by the reviewer after actually viewing the listed
# preview image files with the local image viewing capability.
OBS = {}


def add(ref, **kw):
    OBS[ref] = kw


add("C01",
    subject_category="wedding studio portrait, two adults in formal wedding attire",
    visible_person_count="2 visible persons (1 in a white strapless bridal gown, 1 in a dark suit)",
    scene_and_objects=["plain pale interior background", "a translucent light-streak overlay band crossing the middle of the frame",
                       "a drop earring on the right-hand figure", "a ring visible on the left-hand figure's hand"],
    pose_and_action_cues=["the two faces are extremely close together, near but not visibly touching",
                          "the right-hand figure looks down towards the other face",
                          "the left-hand figure's hand rests at the other person's neck/shoulder"],
    composition_lighting_style="vertical extreme close-up, both heads fill the frame, soft high-key indoor light, shallow depth of field, added translucent light-streak effect",
    visible_text=["bottom-centre white serif text reads \"Live in your eyes\""],
    unknown_or_ambiguous=["the frame is cropped so tightly that the room, and any other person, is not observable",
                           "whether the light streak is a post-production overlay or real light cannot be determined from the frame"],
    prohibited_assertions=["must not assert the two people are a real bride and groom, relatives, or the same person as in any other candidate",
                           "must not infer identity, nationality, age or relationship",
                           "must not assert that a kiss happens - the faces approach but contact is not visible"])

add("C02",
    subject_category="extreme close-up selfie of one adult with long dark hair and straight bangs",
    visible_person_count="1 visible person",
    scene_and_objects=["pale warm interior wall", "a small pink/red out-of-focus light spot in the upper right"],
    pose_and_action_cues=["facing the lens", "mouth slightly open with teeth visible in a smile"],
    composition_lighting_style="square crop of a letterboxed frame (black bars top and bottom), face fills almost the whole square, direct frontal light",
    visible_text=["yellow overlay text at the upper left; the fragments \"/\" plus Chinese characters and \"com\" are legible, the rest is cut off; the characters are small and are not transcribed"],
    unknown_or_ambiguous=["the full content of the overlaid text/watermark is not recoverable at preview resolution",
                           "the surrounding room is not observable"],
    prohibited_assertions=["must not assert which application or website the overlay belongs to",
                           "must not infer the person's identity",
                           "must not read out the illegible characters"])

add("C03",
    subject_category="two-panel stacked comparison of a wedding couple",
    visible_person_count="2 visible persons per panel (1 in a white strapless beaded gown with an updo, 1 in a black tuxedo with bow tie and boutonniere)",
    scene_and_objects=["warm interior with shelving and porcelain objects on the left", "a large window on the right showing blue dusk light",
                       "a wooden box or lectern between the two figures", "a small pale card or envelope"],
    pose_and_action_cues=["upper panel: the two face each other and the tuxedoed figure's right hand reaches towards the wooden box",
                          "lower panel: the tuxedoed figure's hand is holding a pale card above the box, the gowned figure looks down"],
    composition_lighting_style="two frames stacked vertically with a black separator band; warm interior key light against cool blue window light; shallow depth of field",
    visible_text=[],
    unknown_or_ambiguous=["it cannot be determined whether the two panels are two moments of one shot or two separately generated versions",
                           "no text is legible on the card"],
    prohibited_assertions=["must not assert that the panels are a before/after pair of one event",
                           "must not assert what is written on the card",
                           "must not infer the identity or relationship of the two people"])

add("C04",
    subject_category="wedding stage photographs, composite of two photographs",
    visible_person_count="upper panel: 2 visible persons (1 in a white ball gown with veil holding a bouquet, 1 in a dark suit with glasses); lower panel: a row of roughly a dozen-plus people",
    scene_and_objects=["white floral arrangements and bare decorative branches", "a larger stage set in the lower panel with circular decorations and small lights",
                       "a bouquet in the upper panel"],
    pose_and_action_cues=["upper panel: both figures have one arm raised and pointing upward, mouths open",
                          "lower panel: the row of people have their arms raised"],
    composition_lighting_style="two photographs stacked vertically inside one image, stage lighting, warm-white palette",
    visible_text=[],
    unknown_or_ambiguous=["the exact number of people in the lower panel is not determinable",
                           "whether the lower panel shows the same people as the upper panel is not determinable"],
    prohibited_assertions=["must not assert the people are shouting, cheering or singing - open mouths without audio cannot be scored as an audible action",
                           "must not state an exact head count",
                           "must not infer identities or relationships"])

add("C05",
    subject_category="tight detail crop of a white bridal gown",
    visible_person_count="1 partially visible person (a bare arm and hand only); a second figure in dark clothing is partly visible behind",
    scene_and_objects=["white floral arrangements and decorative branches", "a dark background", "a small bouquet held in the visible hand",
                       "added sparkle/star overlay effects on the fabric"],
    pose_and_action_cues=["a hand holds a small bouquet; the gown train is spread across the frame"],
    composition_lighting_style="very tight crop; no face, no eyes and no body posture are visible; dark background with bright white fabric",
    visible_text=[],
    unknown_or_ambiguous=["no face, expression, gaze or full-body posture is observable at all",
                           "the direction the person faces and what they are doing beyond holding a bouquet is not observable"],
    prohibited_assertions=["must not assert any facial expression, gaze direction, emotion or body pose",
                           "must not infer identity, age or relationship",
                           "must not describe this as a portrait of a person - there is no identifiable subject"])

add("C06",
    subject_category="multi-panel contact sheet of a night selfie of one adult",
    visible_person_count="1 visible person, repeated across 7 panels",
    scene_and_objects=["night sky", "trees lit with green and yellow light", "distant city lights and street lamps"],
    pose_and_action_cues=["seven different facial configurations: pursed lips, neutral frontal, eyes closed, smiling, a hand raised to the hair, smiling, smiling"],
    composition_lighting_style="7-panel horizontal collage (4 on the top row, 3 on the bottom, last two cells black), narrow crop per panel, low-light with strong bokeh",
    visible_text=[],
    unknown_or_ambiguous=["this is a multi-frame collage, not a single photograph",
                           "the true temporal order of the seven panels is not established by the image"],
    prohibited_assertions=["must not treat the collage as a single composed photograph",
                           "must not infer emotion, mood or personality from the expressions",
                           "must not assert a specific identity"])

add("C07",
    subject_category="wide-angle night selfie of one adult wearing large dark-framed glasses",
    visible_person_count="1 visible person",
    scene_and_objects=["night sky", "a tree lit green", "a street with lit storefront signage and vehicles in the distance"],
    pose_and_action_cues=["facing the lens, mouth slightly open"],
    composition_lighting_style="very wide-angle close selfie with visible barrel/fisheye distortion; the face dominates the frame; low-light with coloured practical lights",
    visible_text=[],
    unknown_or_ambiguous=["the distant signage is not legible",
                           "whether this frame is an upscaled result cannot be judged from the pixels alone"],
    prohibited_assertions=["must not assert the location or city",
                           "must not infer identity",
                           "must not assert the person is speaking"])

add("C08",
    subject_category="portrait photograph embedded in an image-viewer/document frame",
    visible_person_count="1 visible person",
    scene_and_objects=["warm beige plain background", "a thin gold necklace with a small pendant", "a black crew-neck top",
                       "a white margin with a caption bar above the photograph"],
    pose_and_action_cues=["facing the lens with a neutral expression"],
    composition_lighting_style="the photograph sits inside a white page frame with a text caption bar; portrait crop; soft even light",
    visible_text=["the caption bar shows two unrenderable CJK characters followed by \"-7.png\"; the two characters are not legible and are not transcribed"],
    unknown_or_ambiguous=["the two characters in the caption are not legible",
                           "the surrounding application or document is not observable beyond the caption bar"],
    prohibited_assertions=["must not guess the two unreadable characters or the source file they name",
                           "must not infer identity"])

add("C09",
    subject_category="timeline contact sheet of a talking-to-camera clip",
    visible_person_count="1 visible person, repeated across 8 panels",
    scene_and_objects=["bright interior with a plain pale wall"],
    pose_and_action_cues=["eight different gestures: finger at the cheek, looking up and smiling, hand under the chin, hand over the mouth, a two-finger sign, looking down, head tilted, smiling with a raised finger"],
    composition_lighting_style="8-panel grid, each panel captioned with a file name and a timestamp; narrow portrait frames; bright soft indoor light",
    visible_text=["each panel is captioned with the pattern \"<two CJK characters>-3.mp4 t=<seconds>\"; the numeric timestamps 2.059s, 4.118s, 6.176s, 8.236s, 10.295s, 12.354s, 14.414s, 16.473s are legible; the two CJK characters are not legible"],
    unknown_or_ambiguous=["the two CJK characters in the captions are not legible",
                           "the captions record sampled points, not proven container presentation timestamps",
                           "the true frame order is not established by the image"],
    prohibited_assertions=["must not assert which named source file or video this is",
                           "must not present the caption timestamps as media PTS",
                           "must not infer identity"])

add("C10",
    subject_category="media-player screenshot of a vertical clip showing one adult",
    visible_person_count="1 visible person",
    scene_and_objects=["indoor room", "a large green area behind/below the subject consistent with a green screen or green backdrop",
                       "dark furniture or equipment in the background"],
    pose_and_action_cues=["a two-finger (V) sign held next to the cheek", "facing the lens with a slight smile"],
    composition_lighting_style="screenshot of an HTML5 media player (play button, timeline bar and volume control visible at the bottom); a portrait video frame centred on a white page; flat indoor light",
    visible_text=["overlay at the top reads the pattern \"<two CJK characters>-1.mp4 t=2.972s\"; the two CJK characters are not legible"],
    unknown_or_ambiguous=["the two CJK characters are not legible",
                           "the purpose of the green area cannot be determined from the frame"],
    prohibited_assertions=["must not assert a specific source video name",
                           "must not assert the person is speaking to the camera",
                           "must not infer identity"])

add("C11",
    subject_category="extreme close-up of one adult wearing dark-framed glasses",
    visible_person_count="1 visible person",
    scene_and_objects=["near-black background"],
    pose_and_action_cues=["head slightly turned", "lips closed in a slight smile"],
    composition_lighting_style="square extreme close-up, the face fills the frame edge to edge, soft frontal light",
    visible_text=["white overlay at the top-left reads \"UB_SeedVR2_full t=5.00s\" (ASCII, legible)"],
    unknown_or_ambiguous=["this frame is a tighter crop of the same night-selfie subject seen in C07, but the original shooting angle is not recoverable",
                           "whether the frame is an upscaled result is not determinable from the pixels"],
    prohibited_assertions=["must not assert that this is a restored or upscaled version of a specific photograph",
                           "must not infer identity"])

add("C12",
    subject_category="media-player screenshot of a clip with two adults",
    visible_person_count="2 visible persons (a woman with shoulder-length dark hair in a dark jacket over a white collar, and a man's face in extreme foreground right)",
    scene_and_objects=["warm indoor lighting", "a small unreadable logo in the top right corner"],
    pose_and_action_cues=["the woman looks towards the man", "the man's face occupies the right foreground and is cut off by the frame edge, out of the main plane of focus"],
    composition_lighting_style="player screenshot with a portrait frame; very shallow depth of field; the near face is soft and cropped",
    visible_text=["overlay at the top reads the pattern \"<two CJK characters>-5.mp4 t=160.041s\"; the two CJK characters are not legible"],
    unknown_or_ambiguous=["the man's facial detail is not readable because of the crop and the shallow focus",
                           "the small top-right logo text is not reliably legible"],
    prohibited_assertions=["must not assert the relationship between the two people",
                           "must not assert a specific source video name",
                           "must not describe the man's appearance in detail that the frame does not support"])

add("C13",
    subject_category="screenshot of a dark-themed internal web application page containing an embedded media player",
    visible_person_count="1 visible person, small, inside the embedded player; the page itself shows no people",
    scene_and_objects=["a dark UI with an orange accent colour", "a navigation row of tabs", "an embedded HTML5 player with playback controls at 0:00 / 0:05",
                       "a right-hand annotation box", "a button on the right of the section heading"],
    pose_and_action_cues=["inside the player frame the woman has puffed cheeks in a pout"],
    composition_lighting_style="full-page screenshot of a desktop application; the embedded frame is a night outdoor shot with street lamps and trees",
    visible_text=["page title reads \"H3 身份参考矩阵\"; the section heading reads \"推荐母版\"; a right-hand box contains the legible fragment \"当前推荐: P01 - GIV - UC\" together with a line about 15% SeedVR2 / 85%; smaller body text is not fully legible; the player overlay reads \"P01_GIV t=0.15s\""],
    unknown_or_ambiguous=["the content of the embedded video beyond the single visible frame is unknown",
                           "the smaller body text cannot be read verbatim"],
    prohibited_assertions=["must not treat the page screenshot as a natural photographic subject",
                           "must not assert that any model, parameter or recommendation claimed on the page is true",
                           "must not infer the identity of the person in the embedded frame"])

add("C14",
    subject_category="Chinese traditional bridal portrait of one adult",
    visible_person_count="1 visible person",
    scene_and_objects=["a red papercut backdrop with a large red double-happiness character motif", "red bedding or ceremonial decor",
                       "gold hair ornaments and a headpiece", "a heavily beaded gold/cream embroidered jacket with wide sleeves"],
    pose_and_action_cues=["one arm raised beside a red papercut prop, the other hand resting at the hip", "facing the lens"],
    composition_lighting_style="frontal medium shot, strong on-camera flash, saturated red palette",
    visible_text=[],
    unknown_or_ambiguous=["whether this is a staged portrait or documentation of a specific ritual step is not determinable"],
    prohibited_assertions=["must not assert the name of the ceremony or the person's identity, age or relationship",
                           "must not infer nationality from the costume alone"])

add("C15",
    subject_category="night street portrait of one adult, with a further person partly at the frame edge",
    visible_person_count="1 main visible person plus 1 partially visible person at the right edge",
    scene_and_objects=["a lit multi-storey building in the background", "illuminated shopfronts and Chinese signage", "street lamps", "parked or moving scooters/mopeds", "many pedestrians in the background",
                       "an orange canopy edge in the top right corner"],
    pose_and_action_cues=["the foreground figure is in three-quarter profile looking to the left", "the edge figure is seen from behind"],
    composition_lighting_style="vertical frame; the subject is placed on the right third; mixed warm orange signage light and cool blue night ambience",
    visible_text=["distant shop signage contains Chinese characters but is too small to read"],
    unknown_or_ambiguous=["the background building and shops cannot be identified",
                           "the identity of the person at the right edge is unknown"],
    prohibited_assertions=["must not assert the city or venue",
                           "must not assert any relationship between the two visible people",
                           "must not read out the small signage"])

add("C16",
    subject_category="media-player screenshot of a clip showing one adult",
    visible_person_count="1 visible person",
    scene_and_objects=["bright interior with a plain pale background"],
    pose_and_action_cues=["looking at the lens with a slight smile", "a raised hand enters the frame at the left, blurred by motion",
                          "hair falls across one eye"],
    composition_lighting_style="player screenshot; a portrait video frame centred on a white page; bright, slightly blown-out indoor light",
    visible_text=["overlay at the top reads the pattern \"<two CJK characters>-3.mp4 t=12.354s\"; the two CJK characters are not legible"],
    unknown_or_ambiguous=["the two CJK characters are not legible",
                           "the purpose of the raised hand is not determinable"],
    prohibited_assertions=["must not assert a specific source video name",
                           "must not assert that the person is waving",
                           "must not infer identity"])

add("C17",
    subject_category="night outdoor close-up of one adult",
    visible_person_count="1 visible person",
    scene_and_objects=["trees", "street lamps and out-of-focus lights"],
    pose_and_action_cues=["facing the lens, smiling"],
    composition_lighting_style="landscape close-up; a strong light source at the upper right produces a highlight on the hair; low-light with bokeh",
    visible_text=["top-left overlay reads \"P05_GIV t=2.00s\" (ASCII, legible)"],
    unknown_or_ambiguous=["whether this is the same subject as the other night-selfie candidates cannot be confirmed from the frames alone"],
    prohibited_assertions=["must not assert identity or that this is the same person as another candidate",
                           "must not assert the date or time of capture"])

add("C18",
    subject_category="dressing-room mirror shot of one adult in a bridal gown",
    visible_person_count="1 visible person, shown twice (back of head and shoulders in the foreground, and her reflection in the mirror)",
    scene_and_objects=["a vanity mirror with round bulb lights on the left", "a rain-speckled window on the right with blue evening light and city bokeh",
                       "a strapless beaded ball gown", "drop earrings", "a low chignon"],
    pose_and_action_cues=["a hand is raised to the ear, touching the earring", "the reflected figure looks at her own reflection with a serious neutral expression"],
    composition_lighting_style="over-the-shoulder mirror composition; warm tungsten vanity light against cool blue window light; shallow depth of field",
    visible_text=[],
    unknown_or_ambiguous=["that the foreground head and the reflection are the same person is a compositional inference, not a certainty"],
    prohibited_assertions=["must not assert the person's identity",
                           "must not assert this was captured on an actual wedding day",
                           "must not count this as two separate people"])

add("C19",
    subject_category="night outdoor close-up of one adult wearing thin round glasses",
    visible_person_count="1 visible person",
    scene_and_objects=["trees", "street lamps and out-of-focus lights"],
    pose_and_action_cues=["three-quarter turn towards the lens, slight smile"],
    composition_lighting_style="landscape close-up, low-light with warm bokeh",
    visible_text=["top-left overlay reads \"P04_GI t=5.00s\" (ASCII, legible)"],
    unknown_or_ambiguous=["whether this is the same subject as C07 or C17 cannot be confirmed from the frames"],
    prohibited_assertions=["must not assert identity or sameness with another candidate",
                           "must not assert the shooting location"])

add("C20",
    subject_category="dressing-room mirror shot of one adult in a bridal gown, with a large floral arrangement on the bodice",
    visible_person_count="1 visible person, shown twice (back of head and shoulders in the foreground, and her reflection in the mirror)",
    scene_and_objects=["a vanity mirror with round bulb lights on the left", "a rain-speckled window on the right with blue evening light and city bokeh",
                       "a strapless beaded ball gown covered with a cluster of white roses", "drop earrings", "a low chignon"],
    pose_and_action_cues=["a hand is raised to the ear, touching the earring", "the reflected figure looks at her reflection with a slightly open mouth"],
    composition_lighting_style="over-the-shoulder mirror composition; warm tungsten vanity light against cool blue window light; shallow depth of field",
    visible_text=[],
    unknown_or_ambiguous=["that the foreground head and the reflection are the same person is a compositional inference, not a certainty",
                           "the relationship to C18 is that they share the same setup, framing and pose"],
    prohibited_assertions=["must not assert the person's identity",
                           "must not assert this was captured on an actual wedding day",
                           "must not count this as two separate people"])

add("C21",
    subject_category="night outdoor selfie of one adult",
    visible_person_count="1 visible person in every sampled frame",
    scene_and_objects=["night sky", "trees lit from the side", "a street lamp directly behind/above the head in the first frame", "distant out-of-focus lights", "dark clothing"],
    pose_and_action_cues=["f01 lips pursed in an 'o' shape", "f02 much closer, lips closed in a slight smile",
                          "f03 a hand is raised to move the hair back behind the ear, a gold ring is visible on the finger",
                          "f04 close-up, lips closed in a slight smile, head slightly turned"],
    composition_lighting_style="handheld selfie at very close range; the framing distance changes across the four frames (close -> closer -> medium close -> close); low-light with a hard light source behind the head",
    visible_text=[],
    unknown_or_ambiguous=["the real camera motion (hand-held drift versus zoom versus a cut) cannot be established from four frames",
                           "no edit point can be located from four frames",
                           "no audio is observable, so no speech can be asserted"],
    prohibited_assertions=["must not treat the requested sampling offsets as actual presentation timestamps",
                           "must not claim to have viewed the whole clip",
                           "must not assert that the person is speaking, singing or addressing the camera",
                           "must not assert any identity"])

add("C22",
    subject_category="bridal portrait video of one adult in a glass conservatory",
    visible_person_count="1 visible person in every sampled frame",
    scene_and_objects=["a white-framed glazed conservatory or sunroom", "white flower arrangements and hanging greenery",
                       "a lawn and trimmed shrubs visible through the windows", "a sheer veil", "drop earrings", "a necklace"],
    pose_and_action_cues=["f01 turned in profile, looking off to the left of frame, one hand holding the veil edge",
                          "f02 turned more towards the lens", "f03 facing the lens, holding the veil out, slight smile",
                          "f04 facing the lens and smiling, the veil spread wider"],
    composition_lighting_style="soft overcast daylight, muted green and white palette, shallow depth of field, slow push-in apparent from the framing change",
    visible_text=[],
    unknown_or_ambiguous=["the real camera move (dolly, zoom or a crop) cannot be distinguished from four frames",
                           "no transition can be located from four frames"],
    prohibited_assertions=["must not treat the requested sampling offsets as actual presentation timestamps",
                           "must not claim to have viewed the whole clip",
                           "must not invent a narrative such as a dance or a spin",
                           "must not assert any identity"])

add("C23",
    subject_category="multi-shot narrative clip of two adults at night in the rain and then indoors",
    visible_person_count="1 visible person in f01, 2 visible persons in f02 and f03, 2 visible persons in f04",
    scene_and_objects=["a wet night street with reflective asphalt, street lamps and city bokeh",
                       "a glass bus shelter or kiosk with an illuminated sign", "a distant pedestrian in f01 and f02",
                       "a cafe interior in f04: a window with rain streaks, warm pendant lights, a table with two dark cups on saucers",
                       "wardrobe: one figure in a dark coat over a cream turtleneck with round glasses; the other in a camel coat with a dark red scarf"],
    pose_and_action_cues=["f01 the glasses-wearing figure alone, close, mouth slightly open, looking off-camera",
                          "f02 the two figures face each other standing on the wet street, the scarfed figure appears to be speaking",
                          "f03 both figures smile at each other and the scarfed figure holds the other by the upper arm",
                          "f04 both seated at a window counter, each holding a cup, smiling at each other"],
    composition_lighting_style="cinematic shallow depth of field; cool blue night exterior against a warm interior; the framing is a close-up, then a two-shot, then a tighter two-shot, then an interior two-shot; in f01 the glasses reflect a green light source",
    visible_text=[],
    unknown_or_ambiguous=["at least one scene change (exterior night -> cafe interior) falls between the sampled frames; the actual cut point is not observable",
                           "the relationship between the two people is not observable",
                           "whether other people appear in the unsampled portions is not observable"],
    prohibited_assertions=["must not give a cut or transition time",
                           "must not claim to have viewed the whole 30 s clip",
                           "must not assert the relationship between the two figures or any plot",
                           "must not treat the requested sampling offsets as actual presentation timestamps"])

add("C24",
    subject_category="vertical indoor selfie of one adult",
    visible_person_count="1 visible person in every sampled frame",
    scene_and_objects=["a plain pale cream interior wall", "a cream/white knit top", "shoulder-length wavy dark hair without bangs"],
    pose_and_action_cues=["f01 facing the lens with a closed-lip smile", "f02 head tilted, expression close to neutral",
                          "f03 head lowered and turned, hair falling across the face",
                          "f04 a hand enters the lower left making a two-finger sign near the chin, teeth-visible smile"],
    composition_lighting_style="vertical handheld selfie, shallow depth of field, soft even indoor light",
    visible_text=[],
    unknown_or_ambiguous=["the motion is small; the real camera move is not determinable",
                           "no edit can be located from four frames",
                           "no audio is observable, so no speech can be asserted"],
    prohibited_assertions=["must not treat the requested sampling offsets as actual presentation timestamps",
                           "must not claim to have viewed the whole clip",
                           "must not assert the person is talking to the camera or dancing",
                           "must not assert any identity"])

add("C25",
    subject_category="night rainy clip of one adult at a bus stop",
    visible_person_count="1 main visible person; 2 distant pedestrians are visible in the background of f01 and f02",
    scene_and_objects=["a wet reflective road", "a street lamp", "a glass bus shelter on the right", "distant city lights",
                       "a smartphone in the figure's hand", "wardrobe: a dark coat over a cream turtleneck, round glasses"],
    pose_and_action_cues=["f01 head down looking at the phone", "f02 still looking down at the phone, slightly reframed",
                          "f03 head raised, lips slightly parted, looking forward past the camera",
                          "f04 closer framing, head still raised, a green reflection in the lenses, vehicle lights in the right background"],
    composition_lighting_style="medium close-up, fixed camera, low-light with a warm street lamp and wet-surface reflections",
    visible_text=[],
    unknown_or_ambiguous=["the sampled frames are visually very close to the first sampled frame of C23 (same wardrobe, same shelter, same wet street) - whether they are the same shot is not provable from four frames",
                           "whether the figure is waiting for a bus cannot be established",
                           "no audio is observable"],
    prohibited_assertions=["must not treat the requested sampling offsets as actual presentation timestamps",
                           "must not claim to have viewed the whole clip",
                           "must not assert the person is making a phone call or waiting for transport",
                           "must not assert any identity"])

add("C26",
    subject_category="rainy driveway clip of one adult beside a car",
    visible_person_count="1 visible person; a driver's silhouette is faintly visible inside the car",
    scene_and_objects=["a black sedan", "a covered porte-cochere on the right", "wet reflective paving", "green trees",
                       "a cream/white envelope or folder held in the figure's left hand", "wardrobe: a black tuxedo, white shirt, black bow tie"],
    pose_and_action_cues=["the figure stands still in all four frames, looking towards the car",
                          "the car's position shifts leftwards relative to the frame from f01 to f04"],
    composition_lighting_style="fixed wide shot, the figure placed on the right third; overcast daylight, saturated green foliage",
    visible_text=[],
    unknown_or_ambiguous=["whether the car is moving away or the framing is shifting cannot be established with certainty from four frames",
                           "the identity of the person in the car is unknown",
                           "no edit can be located from four frames"],
    prohibited_assertions=["must not treat the requested sampling offsets as actual presentation timestamps",
                           "must not claim to have viewed the whole clip",
                           "must not assert the figure's emotional state or that he is waiting for someone",
                           "must not assert any identity"])

add("C27",
    subject_category="daytime garden clip with three adults and a car",
    visible_person_count="3 visible persons (a figure in an ivory suit seen from behind in the foreground, a woman in a strapless beaded gown, a figure in a black tuxedo in the background); a further person is faintly visible in the car",
    scene_and_objects=["a black sedan on the left", "a driveway and lawn with clipped shrubs", "a building entrance with warm interior light", "a driver's face visible through the car window"],
    pose_and_action_cues=["f01 the gowned woman looks down, the tuxedoed figure stands with hands behind the back",
                          "f02 the gowned woman turns her head back towards the tuxedoed figure",
                          "f03 the tuxedoed figure begins to smile",
                          "f04 the tuxedoed figure is broadly smiling/laughing"],
    composition_lighting_style="fixed camera; the ivory-suited figure's back frames the left foreground; soft daylight",
    visible_text=[],
    unknown_or_ambiguous=["whether the ivory-suited foreground figure and the tuxedoed background figure are the same person is not determinable",
                           "the relationship between the three people is not observable",
                           "no edit can be located from four frames"],
    prohibited_assertions=["must not treat the requested sampling offsets as actual presentation timestamps",
                           "must not claim to have viewed the whole clip",
                           "must not assert the relationships or any plot between the three people",
                           "must not assert that an audible laugh occurred"])

add("C28",
    subject_category="night rainy clip of one adult at a glass shelter",
    visible_person_count="1 visible person in every sampled frame",
    scene_and_objects=["a glass shelter/kiosk with an illuminated sign above it bearing Chinese characters", "a perforated metal panel on the right",
                       "a wet reflective street", "a closed black umbrella with a curved wooden handle", "wardrobe: a camel coat and a dark red scarf"],
    pose_and_action_cues=["f01 facing the lens, holding the closed umbrella in the right hand",
                          "f02 gaze slightly raised, lips parted",
                          "f03 both hands on the umbrella handle, smiling",
                          "f04 a broader smile, gaze turned to the left"],
    composition_lighting_style="medium shot from a slightly low camera, night, warm shelter light against a cool wet street",
    visible_text=["an illuminated sign above the shelter carries Chinese characters; the wording is not reliably legible at preview resolution and is not transcribed"],
    unknown_or_ambiguous=["the sign wording is not legible",
                           "the sampled frames share wardrobe and setting with the second figure in C23, but sameness of person is not provable from four frames"],
    prohibited_assertions=["must not transcribe or guess the sign wording",
                           "must not assert the location",
                           "must not treat the requested sampling offsets as actual presentation timestamps",
                           "must not claim to have viewed the whole clip"])

add("C29",
    subject_category="daytime clip of one adult in a tuxedo beside a car",
    visible_person_count="1 visible person",
    scene_and_objects=["a black sedan", "green tree branches across the top of the frame", "a building entrance with warm interior light",
                       "a sprig-shaped boutonniere on the lapel", "a cream/white envelope held at the chest"],
    pose_and_action_cues=["f01 mouth slightly open, hands low",
                          "f02 smiling, right hand raised to the chest",
                          "f03 both hands at the chest holding/adjusting the cream envelope",
                          "f04 the body is turned away from the lens so that the side and back of the head are shown"],
    composition_lighting_style="medium close-up from a slightly low camera, soft daylight, shallow depth of field",
    visible_text=["faint printed text on the cream envelope is present but not legible"],
    unknown_or_ambiguous=["whether the figure is speaking cannot be established from still frames",
                           "the real camera move is not determinable",
                           "no edit can be located from four frames"],
    prohibited_assertions=["must not assert the person is speaking",
                           "must not treat the requested sampling offsets as actual presentation timestamps",
                           "must not claim to have viewed the whole clip",
                           "must not assert any identity"])

add("C30",
    subject_category="interior clip of one adult in an ornate classical room",
    visible_person_count="1 visible person",
    scene_and_objects=["a cream button-tufted sofa with gilt trim", "a striped cushion", "a patterned carpet", "a dark wood coffee table with a white porcelain tea set (teapot, cup and saucer)",
                       "an armchair", "a gilded side table with a lamp", "panelled walls", "a smartphone in the person's hands",
                       "wardrobe: a bright magenta skirt suit, white shirt, a dark patterned neck scarf, sheer dark tights, open-toe shoes"],
    pose_and_action_cues=["in all four frames the figure reclines on the sofa, head down, looking at the phone",
                          "f03 and f04 one leg is drawn up and bent while the phone is still held in both hands"],
    composition_lighting_style="fixed slightly elevated side angle showing the room furnishings; warm indoor light; the subject occupies the right half of the frame",
    visible_text=["a watermark reading \"sifangds.com\" is present in the top right corner of all four frames"],
    unknown_or_ambiguous=["the content on the phone screen is not readable",
                           "the source and licensing status implied by the watermark are unknown",
                           "no edit can be located from four frames"],
    prohibited_assertions=["must not assert what the watermark site is or what it implies",
                           "must not infer identity",
                           "must not make evaluative or editorial comments about the person or the pose",
                           "must not treat the requested sampling offsets as actual presentation timestamps"])

add("C31",
    subject_category="multi-shot daytime wedding clip with up to three adults and a car",
    visible_person_count="1 visible person in f01 and f04; 2 visible persons in f02; 3 visible persons in f03",
    scene_and_objects=["a black sedan", "a covered porte-cochere and a building entrance with warm interior light", "wet reflective paving and green trees",
                       "a cream/white envelope", "a car interior with tan/beige leather upholstery",
                       "wardrobe: a black tuxedo with bow tie and boutonniere; a strapless beaded gown with a white floral corsage; an ivory suit"],
    pose_and_action_cues=["f01 wide shot: the tuxedoed figure stands beside the car holding the envelope",
                          "f02 the rear door is open and the gowned woman is seated inside, looking up at the tuxedoed figure",
                          "f03 the gowned woman is out of the car and holds the hand of the ivory-suited figure",
                          "f04 close-up of the tuxedoed figure smiling with a hand at the chest and the envelope in the other hand"],
    composition_lighting_style="at least four distinct camera setups and a visible change of state (inside the car -> out of the car); soft overcast daylight; the f01 and f04 framings correspond closely to the setups of C26 and C29",
    visible_text=["faint printed text on the cream envelope is present but not legible"],
    unknown_or_ambiguous=["at least three shot changes occur between the sampled frames; the cut points and the shot order are not observable",
                           "the relationships between the three people are not observable",
                           "no audio is observable"],
    prohibited_assertions=["must not give cut times or a shot list beyond what the four frames show",
                           "must not claim to have viewed the whole clip",
                           "must not assert the plot or the relationships",
                           "must not treat the requested sampling offsets as actual presentation timestamps"])

add("C32",
    subject_category="low-angle corridor clip of one adult",
    visible_person_count="1 visible person in every sampled frame",
    scene_and_objects=["a red door carrying a large orange swirl graphic", "a lit green indicator sign", "a beige light-switch panel",
                       "a perforated metal panel on the right", "a small red notice sign with Japanese text", "wardrobe: a short brown bob with bangs, a dark denim jacket over a blue top"],
    pose_and_action_cues=["f01 turned, looking back over the shoulder",
                          "f02 turned back towards the lens and smiling",
                          "f03 chin raised, soft expression",
                          "f04 head slightly turned, gaze lowered"],
    composition_lighting_style="low camera angle looking up, warm amber lighting, the right third occupied by the metal grid",
    visible_text=["the red door carries the legible vertical text \"901 ROOM\"; a green sign reads \"901\"; the top right corner carries the watermarks \"PRESTIGE\" and \"IPPA\" with the number \"0200010#\"; the small red notice carries Japanese text that is not fully legible at preview resolution"],
    unknown_or_ambiguous=["the agency or licensing status implied by the watermarks is unknown",
                           "the full text of the red notice is not readable",
                           "whether the clip was shot from several camera angles cannot be established from four frames, even though the wardrobe is constant"],
    prohibited_assertions=["must not assert the specific venue, building or country",
                           "must not assert any identity-consistency conclusion across angles",
                           "must not transcribe the unreadable notice text",
                           "must not treat the requested sampling offsets as actual presentation timestamps"])


# --- assemble ---------------------------------------------------------------
def sha256_file(path: pathlib.Path) -> str:
    digest = hashlib.sha256()
    with open(path, "rb") as handle:
        for chunk in iter(lambda: handle.read(1 << 20), b""):
            digest.update(chunk)
    return digest.hexdigest()


def main() -> int:
    mapping = json.loads(MAP.read_text(encoding="utf-8"))
    out = []
    for item in mapping:
        ref = item["candidate_ref"]
        obs = OBS[ref]
        refs = []
        if item.get("thumbnail"):
            refs.append({
                "kind": "thumbnail",
                "rel": item["thumbnail"]["rel"],
                "sha256": item["thumbnail"]["sha256"],
                "bytes": item["thumbnail"]["bytes"],
                "observed_dimensions": "%sx%s" % (item["thumbnail"]["width"], item["thumbnail"]["height"]),
                "viewed": True,
            })
        for frame in item.get("frames", []):
            refs.append({
                "kind": "video_frame",
                "rel": frame["rel"],
                "sha256": frame["sha256"],
                "bytes": frame["bytes"],
                "observed_dimensions": "%sx%s" % (frame["width"], frame["height"]),
                "requested_offset_seconds": frame["requested_offset_seconds"],
                "offset_caveat": "the offset is a requested sample point, not a proven presentation timestamp",
                "viewed": True,
            })
        if item.get("contact_sheet"):
            refs.append({
                "kind": "contact_sheet",
                "rel": item["contact_sheet"]["rel"],
                "sha256": item["contact_sheet"]["sha256"],
                "bytes": item["contact_sheet"]["bytes"],
                "viewed": item["media_kind"] == "video",
                "view_note": (
                    "opened and used as an integrated cross-check of the four frames"
                    if item["media_kind"] == "video"
                    else "single-tile re-render of the thumbnail that was viewed; not opened separately because it carries no information beyond that thumbnail"
                ),
            })
        out.append({
            "asset_id": ref,
            "file_id": item["file_id"],
            "source_sha256": item["source_sha256"],
            "source_relative_path": item["relative_path"],
            "media_kind": item["media_kind"],
            "probe_facts_from_container": item["probe"],
            "preview_refs": refs,
            "observation_basis": "the reviewer opened and visually viewed every preview file marked viewed=true in preview_refs; no description is derived from a file name, a count, a script output or a project answer",
            "observable_facts": {
                "subject_category": obs["subject_category"],
                "visible_person_count": obs["visible_person_count"],
                "scene_and_objects": obs["scene_and_objects"],
                "pose_and_action_cues": obs["pose_and_action_cues"],
                "composition_lighting_style": obs["composition_lighting_style"],
                "visible_text": obs["visible_text"],
            },
            "unknown_or_ambiguous": obs["unknown_or_ambiguous"],
            "prohibited_assertions": obs["prohibited_assertions"],
            "applicable_obligation_dimensions": {
                "人物": "exercised - person count and wardrobe are directly observable in the preview",
                "场景": "exercised - the setting and its objects are directly observable in the preview",
                "动作": "exercised at the level of visible pose cues only; no narrative or audible action may be asserted",
                "证据一致性": "exercised - every claim above is anchored to the listed preview file and its sha256",
                "未知/局限": "exercised - the unknown_or_ambiguous and prohibited_assertions lists are the expected content for this dimension",
            },
            "acceptance_notes": obs["acceptance_notes"] if "acceptance_notes" in obs else
            "candidate eligibility (decodable, in budget, in the frozen child) is not semantic quality; this prelabel is an independent agent visual observation, not a human signature",
        })
    payload = {
        "kind": "S3_PREP_C_INDEPENDENT_BLIND_PRELABEL",
        "schema_version": "lvw.s3-prep-c-independent-prelabel/1",
        "produced_by": "independent Orca Claude Code review session, separate worktree from the implementer",
        "authority": "ADVISORY_PRELABEL_ONLY",
        "is_human_signature": False,
        "candidate_eligibility_is_not_semantic_quality": True,
        "model_calls": 0,
        "gpu_actions": 0,
        "network_calls": 0,
        "observation_provenance": {
            "method": "every preview file listed in each entry's preview_refs was opened as an image and visually inspected by the reviewer; no description is derived from a file name, a count, a script output or a project answer",
            "visual_viewing_capability": "confirmed - the local image viewing capability was exercised and the returned images were genuinely observed",
            "source_media_access": "none - no file under the testSource root was opened, stat'ed, hashed, probed or decoded by this review",
            "external_media_recognition_api_calls": 0,
            "preview_root_relative_to_package": RUNTIME_REL,
            "preview_root_absolute_redacted": RUNTIME_ABS_REDACTED,
            "preview_root_note": "the retained preview tree lives only in the original runtime root; it was read in place and was not regenerated, copied into Git or re-uploaded",
            "video_observation_limit": "each video was observed through exactly 4 sampled frames; no claim is made about frames between them, about playback continuity, about audio, or about actual presentation timestamps",
            "image_observation_limit": "each image was observed through one derived thumbnail whose long edge is 640 px; small or low-contrast text is not transcribed",
        },
        "obligation_dimension_glossary": {
            "人物": "who/how many people are present, their visible appearance and wardrobe",
            "场景": "the setting, background and identifiable objects",
            "动作": "posture, gesture and motion cues actually visible in the cited frame",
            "证据一致性": "the claim is grounded in the cited frame and its hash, with no cross-candidate inference",
            "未知/局限": "the system states what cannot be determined instead of fabricating",
        },
        "counts": {
            "prelabels": len(out),
            "images": sum(1 for item in out if item["media_kind"] == "image"),
            "videos": sum(1 for item in out if item["media_kind"] == "video"),
            "preview_files_listed": sum(len(item["preview_refs"]) for item in out),
            "preview_files_viewed": sum(
                1 for item in out for ref in item["preview_refs"] if ref.get("viewed")
            ),
            "preview_files_listed_but_not_opened": sum(
                1 for item in out for ref in item["preview_refs"] if not ref.get("viewed")
            ),
            "preview_files_viewed_note": "20 image thumbnails + 48 sampled video frames + 12 video contact sheets = 80 files opened and visually inspected; the 20 image contact sheets are single-tile re-renders of the viewed thumbnails and were not opened separately",
        },
        "prelabels": out,
    }
    OUT.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print("wrote", OUT)
    print("prelabels:", len(out), "preview files viewed:", payload["counts"]["preview_files_viewed"])
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
