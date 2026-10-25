# Video script

Ten minutes, two parts of five. Record the screen with the app at http://localhost:8000 (or the deployed URL) and a small camera or a voiceover. Start on the desk with no query string, so the page is N2EX, bid at the gate, decision day Wednesday 14 January 2026. Speak a little inside the times. The lines below are the words, not a teleprompter to rush.

Evaluation of the submission starts with this video. Do not submit without the unlisted YouTube link.

## Part 1. The desk. Five minutes.

Open on Thursday 15 January. The heading is the delivery day. Read the first sentence and stop.

"This is the wind number you could have bid. Wednesday 14 January, Nord Pool GB, gate 09:50 GMT. The last issue that was out in time was 09:30, twenty minutes before the gate. It counted on 280.3 gigawatt hours. Outturn was 253.6. The day was short 26.6 gigawatt hours of wind."

Point at the chart. The solid line is the issue. The second line is outturn. The fill between them is the miss, and almost all of it sits above outturn. The dashed line is the same issue with a haircut taken from the other days of January.

"The 09:30 issue is the bid. The tape above the chart is every other issue Elexon published that morning. The ones before the gate were usable. They were not the bid, because a later complete issue had already arrived."

Click 11:30.

"11:30 is on the chart now, and it is marked too late. It was published one hour and forty minutes after the 09:50 gate. It counted on 282.2 gigawatt hours against the same 253.6 of outturn, short 28.6. Waiting past the gate made the day worse, not better."

Click 09:30 again so the bid is back.

"The haircut is a share, not a fixed megawatt number, because the miss is larger when the forecast is larger. On this day the share, fit on the other thirty delivery days and not on this one, is 13.4 percent. Counting on 242.7 gigawatt hours would have left the day long 10.9. That is the size of the allowance. It is not a promise for February."

Click Accuracy.

"Across the thirty-one days you bid in January, the 09:30 issue was high by 1,730 megawatts on average. It was above outturn on 627 of 744 hours, and the energy was short on 28 of 31 days. You would have counted on 9,682 gigawatt hours. You got 8,395. The gap is 1,287 gigawatt hours."

Point at the histogram, then click After the haircut.

"The mass to the right of zero is wind you counted on and did not get. After the haircut the mass sits on zero, and a tail remains. In the calmest fifth of hours the average miss was about 330 megawatts. In the windiest fifth it was about 3,580. A flat megawatt haircut, tested by leaving each day out, still misses by 1,435 megawatts. The share misses by 1,212."

Point at the issue table, then at the day bars. Click the tall bar, delivery day 28 January, short about 129 gigawatt hours.

"The 02:30 issue and the 09:30 issue are almost the same miss, 2,073 against 2,013. The 22:30 issue, which you could not have bid, is 1,825. A fresher forecast is not where the money is. The level is. The largest short day is 28 January."

Close on that book for a moment, then say:

"We did not load your demand, and we did not load a price, so this does not tell you what to pay. It tells you the wind you were allowed to believe at the gate, and how many megawatts to take off it. EPEX hourly closes at 09:20, before the 09:30 issue, so that bid uses 07:30. If you need thirty minutes to get the N2EX bid in, you also lose 09:30. Both of those are on the controls at the top."

## Part 2. The review. Five minutes.

Switch to the repository. Start with the shape, then the rule, then the files.

"The extracts are committed as JSON. `python -m daymark.build` turns them into SQLite. FastAPI scores from that store. React only draws the JSON the API returns. The Docker build runs the frontend build, the database build, and pytest, and the image will not start if the January figures move. OpenAPI is at `/docs` on the same process."

Open `backend/daymark/auctions.py`.

"Three gates, in GMT, because that is how they are published. N2EX 09:50, EPEX hourly 09:20, EPEX half-hour 15:30. January is GMT, so London and the auction clock match. The cutoff is the gate minus 0, 15, or 30 minutes. The bid is the latest issue at or before the cutoff that covers at least 20 of the 24 hours. A short fragment cannot knock out a complete older issue. One issue for the whole day."

Open `backend/daymark/analysis.py` and show `choose_issue`, then the hourly score.

"WINDFOR is hourly. FUELHH wind is half-hourly. The book holds the hourly forecast flat across the two settlement periods, which is all the shape the forecast has. The headline error scores the hour once, forecast minus the mean of the two outturns. Scoring both halves would count the same forecast twice. Energy is megawatts times one hour, and times a half hour in the book."

Show the haircut.

"k is total error divided by total forecast on the other delivery days. It is applied to the day on screen, including a counterfactual issue. The same leave-one-day test is how the accuracy page compares the share with a constant megawatt haircut. Persistence is yesterday's same hour. The within-month hour average uses the other days, so it is a description, not a bid you could have made. Thursday 15 January has a 12:25 issue instead of 11:30. The note is generated by comparing each day with the usual set of slots. We do not fill a missing slot."

Open `backend/tests/test_january.py` and `backend/tests/test_analysis.py`.

"The January test locks the N2EX figures: 2,013 megawatts MAE, the 09:30 slot on all 31 days, and the single note about 15 January. The unit tests lock the gate choice, including EPEX hourly falling back to 07:30, a 30-minute lead falling back to 07:30, the half-hour auction taking the 15:30 issue, a 10-hour fragment losing to a complete issue, and the hour not being double-counted. Twelve tests. The image runs them."

Open `frontend/src/pages/Desk.jsx`, then `speech.js`, then `Tape.jsx`.

"The page state is the query string: auction, lead, date, issue, demand. The sentences are built from the API payload, not typed in. Demand is parsed in the browser and is not sent. The tape labels an issue as in the bid, usable, too late for the lead, or after the gate."

Close on practices.

"The raw JSON is the source of truth, about two megabytes, and the database is rebuilt. There is no Elexon key. CORS is limited to the Vite origin. A bad date, a bad auction, and an unknown issue return a 400 with a sentence, not a stack trace. The sign convention is in the footer of every page. What this will not do is in Method: no demand series, no pounds, no embedded-wind adjustment, and the cushions are percentiles of this month, not a probability for a new day."
