# Demo script — questions Mitra answers well

**Captured:** 2026-08-29 (re-verified after the second live session) against `qwen3-vl:8b-instruct`, the 500-verse corpus and the
981-row phrasebook, via `scripts/dry_run.py` (the real pipeline: same agent, same
retrieval, same checks — only the microphone and the speaker are stubbed).

This is a **script for a live demo**, not a specification. Every line below was
actually produced by the local model in that run, and the ones that were not are
listed at the bottom under *What to avoid*, with the reason each failed. The exact
Sanskrit varies between runs (`temperature: 0.3`); what is stable is the **shape** —
that a reply comes, that it is about what you said, and that it ends with a question
you can answer.

**How to run it:** `python3 main.py --debug`, then say **"Hey Mitra"** and wait for
the greeting. Speak one line at a time and let Mitra finish — the microphone is
deliberately deaf during playback, so a line spoken over the reply is lost.

---

## The script

Read down the left column. Mitra's question at the end of each reply is what makes
the next line of the script the natural thing to say.

| # | You say | Mitra answers | …and asks back |
|---|---|---|---|
| 1 | Hello Mitra, how are you? | अहं अपि कुशलः अस्मि। *(I am well too)* | त्वं कथम् असि? *(How are you?)* |
| 2 | I am fine too. | मह्यम् अपि कुशलः अस्मि। *(I am well too)* | तव दिनं कथम् अस्ति? *(How is your day?)* |
| 3 | What is your name? | मम नाम मित्रम्। *(My name is Mitra)* | तव नाम किम्? *(What is your name?)* |
| 4 | **My name is Tafik.** | स्वागतं तफिक! *(Welcome, Tafik!)* | त्वं कुत्र वससि? *(Where do you live?)* |
| 5 | I live in Bangalore. | बैंगलोरं सुन्दरं नगरम् अस्ति। *(Bangalore is a beautiful city)* | तव मित्रस्य नाम किम्? *(What is your friend's name?)* |
| 6 | What is your favourite food? | मह्यं क्षीरं रोचते। *(I like milk)* | तुभ्यं किं रोचते? *(What do you like?)* |
| 7 | I like milk too. | गावः क्षीरं ददति। *(Cows give milk)* | तत् तुभ्यं किमर्थं रोचते? *(Why do you like it?)* |
| 8 | What do you play? | अहं कन्दुकेन क्रीडामि। *(I play with a ball)* | त्वं किं क्रीडसि? *(What do you play?)* |
| 9 | What are you reading? | अहं पुस्तकं पठामि। *(I am reading a book)* | त्वं किं पठसि? *(What do you read?)* |
| 10 | **Can you tell me a shloka?** | *a verse from the corpus, with its colophon* | एषः श्लोकः तुभ्यं रोचते वा? *(Did you like this verse?)* |
| 11 | Yes, I liked it. | *(a remark of its own)* | अन्यं श्लोकं श्रोतुम् इच्छसि वा? *(Shall I recite another?)* |
| 12 | **Yes please.** | *a second verse* | त्वम् अपि श्लोकं जानासि वा? *(Do you know a verse too?)* |
| 13 | Yes, I know one shloka. | *a third verse* | एषः श्लोकः तुभ्यं रोचते वा? |
| 14 | Goodbye Mitra. | पुनः मिलामः। *(See you again)* | — *(a farewell is never followed by a question)* |

Four turns are worth watching for, because each is a piece of machinery rather than
a lucky generation:

- **Turn 4 — your name.** Every check downstream of the model rests on a closed list
  of words Mitra may say, and a name arrives from outside it. Before this branch,
  this exact turn answered *"क्षम्यताम्, अहं न अवगच्छामि"* ("sorry, I do not
  understand"), because तफिकः is correctly not a Sanskrit word (FR-3.15). Any name
  works; a rare one is a better demo than "Ravi".
- **Turns 6→7 and 11→12 — the conversation goes deeper.** When you *answer* a
  question instead of asking one, the next question belongs to the same subject:
  *what do you like* → *why do you like it* → *what else do you like*. Two steps per
  subject, then Mitra changes the topic (FR-3.12). Answer with a statement, not a
  question, or you will restart the subject instead of deepening it.
- **Turn 12 — "yes" is heard as a request.** *"Shall I recite another?"* answered
  with "yes" reaches the verse corpus, not the model (FR-3.16). The verse is
  recited from a 500-row corpus of real poets — it is never generated.
- **Turn 13 — the word does the work.** Saying "shloka" at all is treated as a
  request for one, deliberately: a person does not say the word to a Sanskrit robot
  for any other reason, and a missed request costs the whole feature. If you want
  Mitra to *react* to your answer instead, say "Yes, I know a small one" without
  the word.

## Spare questions, same run, same result

Any of these can be dropped in; each got a sensible one-sentence answer and a
question back.

| You say | Mitra answered |
|---|---|
| What are you doing? | मह्यम् अपि कार्यं करिष्यामि। |
| Where do you live? | अहं नगरे अवस्थितः। *(I live in a city)* |
| What will you do today? | अद्य अहं पठिष्यामि। *(Today I will read)* |
| Do you like music? | मह्यम् अपि संगीतं रोचते। |
| Who is at your home? | क्षम्यताम्, अहं गृहे न अस्मि। *(Sorry, I am not at home)* |
| Are you my friend? | अहं भवतः मित्रम् अस्मि। *(I am your friend)* |

And these keep a subject alive once it is open — say them as **statements**, so the
turn deepens rather than jumping:

- "I like milk too." · "I live in Bangalore." · "I am fine too." · "I read every day."

## What to avoid, and why

Measured in the same run — these are model limits, not bugs to route around live:

- **"What does that mean in English?"** after a verse. Asked three ways, the model
  answered about a different verse, or about milk, or ran past its context window.
  A verse is recited from the corpus and never passes through the model, so it has
  no reading of its own to give — and a wrong meaning taught as scripture is exactly
  what the corpus exists to prevent. Mitra therefore never offers to explain one.
- **English loanwords in the thing you name** — "cricket", "a ball game". The model
  invents a Sanskrit-shaped word for them (गोलाकारेण, पिटकेन), the morphology check
  rejects it, and after one retry the turn ends in the safe fallback. Name things
  the beginner vocabulary has: a book, a ball, milk, a garden, a tree.
- **Naming an animal.** *"What is your favourite animal?"* is a coin flip: the model reaches past cat, dog and elephant — all of which it can say — for a sheep, a rooster, or a misspelt श्वान, and the turn ends in the safe fallback about half the time. Ask it if you want to show the checks working; skip it if you want a clean run.
- **"Tell me about the sun."** and **"What do you see outside?"** Open-ended prompts
  with no subject to hold on to; both ended in the safe fallback, one after 60 s.
- **Long or double sentences.** One short line per turn. The ASR is running on the
  CPU and the reply budget is one sentence.
- **Talking over Mitra.** The mic is closed during playback (say "Hey Mitra" to
  barge in deliberately).

## If a turn does end in "क्षम्यताम्, अहं न अवगच्छामि"

That is the safe fallback: the model's reply failed the Sanskrit checks twice. It is
working as designed — the alternative is a child being taught Hindi or an invented
word. Say the line again in simpler words, or move to the next question. The reason
is in the log: `reply failed validation (…)` names the offending word.
