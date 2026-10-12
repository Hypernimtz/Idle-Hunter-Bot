"""
Scene pools for the three choose-your-path events (The Great Fog, Admin Error 404,
Thunderstorm Survival). Pure data.

A run is five scenes drawn at random from the pool. Each choice is
    (label, outcome text, delta to meter A, delta to meter B)
Both meters start at 3 and top out at 6; a run that sends either meter to 0 turns back.
There is deliberately no strictly-best answer — every choice trades one meter for the other.

Choices also carry forward through the run. A scene may carry
    "fx": {choice_index: {"gain": flag, "lose": [flags], "strain": True, "tag": "short memory"}}
    gain   — you now carry something (a rope, a lantern's circle, a ledger page). If the pool has a follow-up scene
             that "needs" that flag, it is slipped into one of the next two scenes — a crossing, a place, a clue.
    lose   — you drop something you were carrying.
    strain — the NEXT scene is harder: every gain it offers is one smaller.
    tag    — the line shown in the run's journey ("Kept the rope").
A scene with "needs": flag only ever appears once you hold that flag, and "uses": [flags] spends them. "because"
is the line that tells the player why they are seeing it. FLAGS holds each pool's (emoji, label) per flag.
"""

SCENES = {

# ─────────────── THE GREAT FOG  ·  meters: Clarity / Nerve ───────────────
"fog": [
    {"id": "f1", "fx": {0: {"gain": "lantern", "tag": "Followed the lantern"}, 2: {"gain": "rag", "tag": "Tied a rag to the trail"}},
     "text": "A lantern is bobbing in the white, some way off the trail. It moves like it's walking — "
                          "but nobody here is carrying one.",
     "choices": [("Follow the light", "The lantern leads you in a wide circle and winks out. You learn the circle's shape.", 2, -1),
                 ("Call out", "Your voice comes back from the wrong direction, a little too cheerful.", -1, 2),
                 ("Mark the trail and wait", "You tie a rag to a branch. When you come back to it, the knot is different.", 1, 0)]},
    {"id": "f2", "fx": {2: {"strain": True, "tag": "Threw a stone at the water"}},
     "text": "The ground goes soft and the fog thickens. Somewhere ahead, water — or something pretending to be.",
     "choices": [("Wade straight through", "Cold to the knee, and then solid. You didn't see the stones until you stood on them.", 0, 1),
                 ("Skirt round the edge", "It takes longer. The fog presses closer the further you go from the water.", 1, -1),
                 ("Throw a stone first", "The splash comes back *twice*. You decide you didn't need to know.", 2, -2)]},
    {"id": "f3", "text": "Footprints. Your own, you realise. They're coming toward you.",
     "choices": [("Walk in them", "They lead somewhere your boots haven't been yet. It's warmer there.", 2, -2),
                 ("Cover them", "You scuff them out with your heel. The fog leans in, hurt.", 0, 1),
                 ("Compare them to yours", "Identical. Down to the loose lace. You re-tie yours, quickly.", 1, 0)]},
    {"id": "f4", "text": "The fog parts for a moment and you see a figure on a ridge — tall, antlered, still.",
     "choices": [("Hold your ground", "It watches you for a long breath, then turns and is gone.", -1, 2),
                 ("Raise your lantern", "Light on antlers. They're not made of bone. They're made of *branches*, and they're blossoming.", 2, -1),
                 ("Back away slowly", "You back into a tree you could swear wasn't there.", 0, 0)]},
    {"id": "f5", "fx": {0: {"gain": "bearings", "tag": "Wrote down the bearings"}, 1: {"strain": True, "tag": "Answered the voice"}},
     "text": "A voice, Odalys Venn's, you think, reading numbers. Bearings and distances. It repeats.",
     "choices": [("Write them down", "You get four of the six bearings before the voice drifts. It's enough to plot a line.", 2, -1),
                 ("Answer her", "The voice stops. \"Oh,\" it says, relieved. \"There you are.\" It does not sound like her any more.", -2, 2),
                 ("Listen without moving", "The numbers loop. You count the loop. It's seven. Seven of everything.", 1, 1)]},
    {"id": "f6", "text": "A wall of white. In it, a door-shaped gap that isn't a door and isn't a gap.",
     "choices": [("Walk through", "It's cold, and for a moment you're *very* small. Then you're through.", -1, 2),
                 ("Throw something in", "It comes back out the other side of you. Gently.", 1, 0),
                 ("Go around", "There is no around. There's only a longer way through.", 0, -1)]},
    {"id": "f7", "fx": {0: {"gain": "map", "tag": "Took the half-finished map"}},
     "text": "You find a camp: fire cold, tent open, a half-finished map pinned under a mug. Fresh ink.",
     "choices": [("Take the map", "You tuck it into your coat. Behind you, the mug begins, softly, to hum.", 2, -1),
                 ("Sit and rest a moment", "You close your eyes for five breaths. When you open them it's an hour later, and nothing has changed.", -1, 2),
                 ("Leave a note", "You write *'I was here too.'* The ink sinks into the page like it was thirsty.", 1, 1)]},
    {"id": "f8", "fx": {0: {"strain": True, "tag": "Looked back at the crater"}},
     "text": "The fog begins to *thin* — not clear, but wrong. You can see too far. Things at the edge of sight "
                          "don't match the distance.",
     "choices": [("Trust your eyes", "You see the crater rim, a great way off, as clearly as your own hand. It sees you back.", 2, -2),
                 ("Close them and walk", "Eleven steps. Twelve. When you look again the real fog has closed round you like a hand.", -1, 1),
                 ("Study one thing", "You pick a stump, and watch it. It does not move. That is, strangely, enough.", 1, 0)]},
],

# ─────────────── ADMIN ERROR 404  ·  meters: Stability / Sanity ───────────────
"404": [
    {"id": "b1", "fx": {2: {"gain": "ticket", "tag": "Filed ticket #404"}},
     "text": "OBJECTIVE: Click the button that isn't there. A button that isn't there is flashing.",
     "choices": [("Click it", "It clicks back. A small dialog: *'Are you sure you meant that?'* You were not.", 1, -1),
                 ("Click the space where it isn't", "Your cursor sinks into the screen up to the wrist. It's quite nice in there.", -1, 2),
                 ("Report it as a bug", "Ticket #404 created: *'button not found'*. Status: closed. Reason: *'working as intended.'*", 2, -1)]},
    {"id": "b2", "fx": {1: {"gain": "counter", "tag": "Fed the counter a banana"}},
     "text": "OBJECTIVE: The ammo counter reads *banana*. Fix it.",
     "choices": [("Type '100'", "It says 100. Then *banana 100*. Then *100 banana*. Then it settles on 'banana'.", -1, 1),
                 ("Feed it a banana", "The counter eats the banana. It reads *'thank you'*.", 1, 1),
                 ("Turn it off and on again", "Everything goes dark for one second. When it returns, the counter says 'apple'. Progress.", 1, 0)]},
    {"id": "b3", "fx": {2: {"strain": True, "tag": "Merged the hunters"}},
     "text": "OBJECTIVE: A hunter appears in two places at once. Find the real one.",
     "choices": [("Ask them both", "\"I'm the real one,\" they both say, in the exact same voice, at the exact same time.", 0, 1),
                 ("Wait and see which blinks first", "Neither blinks. Both blink. You decide this is somebody else's problem.", 1, -1),
                 ("Merge them", "A loud 'ding'. There's now one very smug hunter holding two lunches.", 2, -2)]},
    {"id": "b4", "fx": {1: {"strain": True, "tag": "Poked the loading bar"}},
     "text": "OBJECTIVE: The loading bar is at 99%. It has been at 99% for eleven days.",
     "choices": [("Wait politely", "At 99.0001% a tiny voice says *'almost'*. It's the loading bar. It's apologetic.", 0, 1),
                 ("Poke the bar", "It rolls over like a dog. Underneath it says: *'ok fine. 100%.'* It lies.", 2, -2),
                 ("Reinstall everything", "You uninstall the camp. The camp reinstalls itself, with a few improvements.", 1, 0)]},
    {"id": "b5", "text": "OBJECTIVE: A tooltip insists the door is a window. The window insists it is a wall.",
     "choices": [("Agree with the tooltip", "The door becomes a window. You climb through it with great dignity.", 0, 1),
                 ("Walk through the wall", "You are in the next room. The next room is the same room.", 1, -1),
                 ("Argue with the wall", "You win. The wall files a complaint. The complaint is a door.", -1, 2)]},
    {"id": "b6", "fx": {0: {"gain": "mug", "tag": "Kept the Admin's mug"}},
     "text": "OBJECTIVE: The Admin's chair is spinning. Nobody is in it.",
     "choices": [("Stop it", "It stops. Then it sighs, as if something finally let go. A coffee mug appears.", 1, 1),
                 ("Sit in it", "You are now the Admin. For eleven seconds. It's a lot. You stand up.", -2, 2),
                 ("Spin it faster", "It leaves the ground. It hits the ceiling. The ceiling is polite about it.", 2, -2)]},
    {"id": "b7", "text": "OBJECTIVE: A pop-up says *'You have 1 unread notification.'* It has been following you for a while.",
     "choices": [("Read it", "*'You have 1 unread notification.'* It is a very good one.", -1, 1),
                 ("Close it", "It closes. Another opens, exactly the same, with a slightly hurt expression.", 1, -1),
                 ("Mark as read", "Peace. Briefly. Then it says *'You have 0 unread notifications. Why?'*", 1, 0)]},
    {"id": "b8", "text": "OBJECTIVE: The world's gravity setting has been changed to *'whimsical'*.",
     "choices": [("Float", "You float. It's lovely. You drift gently into the lamp-oil store.", -1, 2),
                 ("Hold onto something", "You hold onto the camp's flagpole. The flagpole holds onto you back.", 1, 0),
                 ("Set it back to normal", "Settings → Physics → Gravity. A dropdown: *whimsical, silly, very silly, normal (locked).*", 2, -1)]},
],

# ─────────────── THUNDERSTORM SURVIVAL  ·  meters: Supplies / Morale ───────────────
"storm": [
    {"id": "s1", "fx": {0: {"strain": True, "lose": ["rope"], "tag": "Abandoned half the tents"}, 1: {"gain": "rope", "tag": "Kept the rope and tents"}},
     "text": "The wall of cloud is two hours out. The camp still has tents to strike and a long march to shelter.",
     "choices": [("Pack light, move now", "You leave half the tents and gain half the day. Everyone's lighter. Not everyone is happy.", -1, 1),
                 ("Strike everything", "It takes the full two hours. You make the cliffs with the first rain on your neck.", 1, -1),
                 ("Split the group", "Two columns, two routes. They meet again at dusk with matching stories.", 0, 1)]},
    {"id": "s2", "fx": {2: {"strain": True, "lose": ["rope"], "tag": "Cut the heavy packs loose"}},
     "text": "Thunder rolls up the valley and the pack animals refuse to move another yard.",
     "choices": [("Unload and carry it yourselves", "A hard slog, but nobody's left standing in the open.", -1, 1),
                 ("Calm them with food", "You spend rations you'd have wanted later. The mules walk on, chewing.", -1, 2),
                 ("Cut the heaviest packs loose", "You lose some gear but gain a lot of speed.", 1, -1)]},
    {"id": "s3", "fx": {0: {"gain": "overhang", "tag": "Found a dry overhang"}},
     "text": "Lightning splits a pine across the path ahead. It's burning, and the wind is carrying the sparks.",
     "choices": [("Go round through the rocks", "Slower, but wet stone doesn't burn.", 0, 0),
                 ("Clear it and go through", "A tough, hot hour. You lose a pair of gloves and one boot's tread.", -1, 1),
                 ("Wait for the rain to put it out", "It does. Eventually. Everyone is very cold by then.", 1, -2)]},
    {"id": "s4", "text": "A river that was a stream this morning is a brown, roaring thing. The only bridge is gone.",
     "choices": [("Rope across", "Slow and careful. Everyone is wet. Nobody is lost.", -1, 1),
                 ("Find another crossing", "Two hours' walk upstream, through bad ground.", 0, -1),
                 ("Fell a tree for a bridge", "It works — loudly, and with a great deal of shouting.", -1, 2)]},
    {"id": "s5", "text": "Night. The storm has settled right on top of you. The tents are screaming and nobody can sleep.",
     "choices": [("Sing", "Badly. All night. By dawn there are four songs and a rule against the fifth.", 0, 2),
                 ("Share the last of the tea", "Warm hands, warm hearts, empty tin.", -1, 1),
                 ("Ration out silence and sleep", "Quiet, cold, efficient. Not the worst night anyone's had.", 1, -1)]},
    {"id": "s6", "text": "Someone's twisted their ankle and the trail narrows to a ledge over a long drop.",
     "choices": [("Carry them", "Two hunters take turns. It slows everyone down and nobody complains.", 0, 1),
                 ("Splint and move on", "A tight splint, a steady pace, and a brave face.", 1, -1),
                 ("Make camp until the weather turns", "Safe. Comfortable-ish. And a day's supplies gone.", -2, 2)]},
    {"id": "s7", "fx": {2: {"gain": "ledger", "tag": "Logged the storm in the ledger"}},
     "text": "A crack of thunder so loud it rings. In the ringing, the storm says its three words again: *'Bring it back.'*",
     "choices": [("Answer: \"Bring what?\"", "A long, thinking silence. The rain eases for a moment, as if surprised.", -1, 2),
                 ("Cover your ears and march", "You march. The words stay with you anyway.", 1, -1),
                 ("Write it in the ledger", "Ione will want this. You record the exact time and pitch.", 1, 0)]},
    {"id": "s8", "text": "Dawn on the third day. The rain has stopped, but the clouds haven't gone — they're waiting, "
                          "low and green.",
     "choices": [("Push on while it's quiet", "A mile before the next band. You make it to a ridge and look back.", -1, 1),
                 ("Rest and dry out", "Boots by the fire. Morale rises, supplies don't.", -1, 2),
                 ("Scout ahead first", "Your scout returns with good news and a muddy tail.", 1, 0)]},
],
}


# What the player can be carrying, per pool: flag -> (emoji, label).
FLAGS = {
    "fog": {
        "lantern":  ("🏮", "the lantern's circle"),
        "rag":      ("🪢", "a rag on the trail"),
        "bearings": ("🧭", "Odalys's bearings"),
        "map":      ("🗺️", "Odalys's half-map"),
    },
    "404": {
        "ticket":  ("🎫", "ticket #404"),
        "counter": ("🍌", "a friendly ammo counter"),
        "mug":     ("☕", "the Admin's mug"),
    },
    "storm": {
        "rope":     ("🪢", "the rope"),
        "overhang": ("⛰️", "a dry overhang"),
        "ledger":   ("📓", "Ione's ledger"),
    },
}

# Follow-up scenes: only offered once the player holds the flag they `need`.
FOLLOWUPS = {
"fog": [
    {"id": "fx1", "needs": "lantern", "uses": ["lantern"], "title": "The Standing Stone",
     "because": "🏮 The lantern's circle closes on somewhere new.",
     "text": "The circle you walked closes on something the fog hasn't swallowed: a standing stone ringed with cold lantern-wax. "
             "It wasn't on any map until you walked its shape.",
     "choices": [("Read the carvings", "Odalys's hand again — a sketch of the crater and an arrow back to camp. You copy it down.", 2, -1),
                 ("Rest against the stone", "The stone is warm. For a little while the fog forgets you.", 1, 1),
                 ("Chip off a sample", "It rings like a bell. Everything listening turns toward you.", 1, -2)]},
    {"id": "fx2", "needs": "rag", "uses": ["rag"], "title": "The Rag, Retied",
     "because": "🪢 You marked the trail, and the trail remembers.",
     "text": "A rag hangs from a branch ahead — yours, with a different knot. You have walked a circle, and now you know "
             "exactly where the circle is.",
     "choices": [("Cut across the loop", "You break the circle by walking straight through its middle. The fog sulks.", 1, 0),
                 ("Follow the rags home", "Every rag you tied is still there, and every one has been retied better. A gift, or a lesson.", 0, 2),
                 ("Add another rag", "You tie a second, then a third. The branch begins to look like a flag of surrender.", -1, 1)]},
    {"id": "fx3", "needs": "bearings", "uses": ["bearings"], "title": "A Straight Line",
     "because": "🧭 Four of the six bearings are on your sleeve.",
     "text": "The bearings you plotted in charcoal run into a single point out in the white. There's something there, or someone.",
     "choices": [("Walk the line exactly", "Step for step, bearing for bearing. At the end, a lantern set down carefully. Still warm.", 2, -1),
                 ("Fill in the missing two", "You guess the last bearings. The line bends, politely, to meet them.", 0, 1),
                 ("Shorten the walk", "You cut a corner. The fog cuts it back, a little further along.", -1, 2)]},
    {"id": "fx4", "needs": "map", "uses": ["map"], "title": "The Missing Margin",
     "because": "🗺️ You are carrying Odalys's half-finished map.",
     "text": "The half-finished map has a river bend not yet drawn — and you are standing on it. The ink on the page is still wet.",
     "choices": [("Finish her line", "Your pen follows hers as if it knew the way. The map hums.", 2, -1),
                 ("Draw it in your own hand", "It doesn't match hers, and the fog seems relieved to be disagreed with.", 1, 0),
                 ("Leave the margin blank", "You keep the gap clean. Something, somewhere, is relieved.", -1, 1)]},
],
"404": [
    {"id": "bx1", "needs": "ticket", "uses": ["ticket"], "title": "Ticket #404, Reopened",
     "because": "🎫 Your ticket got a reply.",
     "text": "A reply to your ticket, in your own handwriting: *'We have escalated this to ourselves.'* It's signed. "
             "It is also, somehow, due today.",
     "choices": [("Reply \"thanks\"", "Marked resolved. The ticket sends a small, glowing fruit basket.", 1, 1),
                 ("Escalate it further", "You escalate to the Admin. The Admin escalates to the console. The console files a complaint about you.", 2, -2),
                 ("Close it without reading", "Closed. Instantly reopened, with a slightly hurt expression.", -1, 1)]},
    {"id": "bx2", "needs": "counter", "uses": ["counter"], "title": "The Grateful Counter",
     "because": "🍌 The ammo counter remembers you.",
     "text": "The ammo counter reads *'thank you'*, then *'door →'*. A door appears, marked *definitely not a door*.",
     "choices": [("Take the not-door", "It is, in fact, a door. A very good one.", 2, -1),
                 ("Feed the counter another banana", "*'two bananas'*. Then *'three'*. Then, politely, *'stop'*.", 1, 1),
                 ("Ask where the door leads", "The counter reads *'banana'*. Progress, you suppose.", -1, 1)]},
    {"id": "bx3", "needs": "mug", "uses": ["mug"], "title": "The Mug Is Still Warm",
     "because": "☕ You kept the mug from the Admin's chair.",
     "text": "The mug from the Admin's chair is still warm. It has begun, quietly, to hum a tune you almost know.",
     "choices": [("Drink from it", "It tastes like Tuesday. You feel briefly, unreasonably competent.", 1, 1),
                 ("Ask the mug for advice", "It suggests turning everything off and on again. It's right, annoyingly.", 2, -1),
                 ("Put it down", "The mug sighs and goes cold. You feel a little rude.", -1, 0)]},
],
"storm": [
    {"id": "sx1", "needs": "rope", "uses": ["rope"], "title": "A Gap in the Ledge",
     "because": "🪢 You kept the rope.",
     "text": "The trail ends in a gap between two wet rocks: too wide to jump, too narrow to be worth a detour. "
             "The rope on your shoulder suddenly feels very lucky.",
     "choices": [("Rig a line and cross everyone", "Anchor, tension, one at a time. Slow, soaking, and not a single person lost.", 0, 2),
                 ("Cross alone and haul the rest", "Fast on your side, slow on theirs. The rope sings.", 1, -1),
                 ("Throw the rope across and leave it", "It holds. You lose the rope, but you're over before the next band.", 1, 0)]},
    {"id": "sx2", "needs": "overhang", "uses": ["overhang"], "title": "The Overhang",
     "because": "⛰️ You remembered the dry rock.",
     "text": "The overhang you marked is right where you left it: dry rock, wide enough for everyone, with the wind "
             "howling harmlessly past.",
     "choices": [("Shelter everyone and wait out the band", "Dry socks, dry spirits. Not a minute wasted that wasn't needed.", 0, 2),
                 ("Rest an hour and move on", "A short stop. Everyone is steadier for it.", 1, 1),
                 ("Cook a proper meal", "A feast, by storm standards. The pot is empty by the end.", -2, 2)]},
    {"id": "sx3", "needs": "ledger", "uses": ["ledger"], "title": "The Ledger's Pattern",
     "because": "📓 Ione's ledger has the storm's timings.",
     "text": "You open the ledger to the page you wrote: every thunderclap, timed. Between the bands there are eleven "
             "minutes of quiet. It's almost a schedule.",
     "choices": [("Move in the quiet", "Eleven minutes, and you use every one of them.", 1, 1),
                 ("Send word ahead", "A runner with the timings. The camp is ready when you arrive.", 0, 2),
                 ("Add this one's timing too", "You stop to write it down. The next band catches you flat-footed.", 2, -2)]},
],
}
for _pool, _extra in FOLLOWUPS.items():
    SCENES[_pool].extend(_extra)
