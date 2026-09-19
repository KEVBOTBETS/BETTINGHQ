# Pregame accuracy integrity repair — 2026-09-19

Pending forecasts and shadow calls used to be overwritten after first pitch.
The subsequent grading step therefore scored live/postgame projections and
could feed them back into calibration. The original `first_seen` timestamp
does not rescue a later overwritten forecast.

Both recording paths now stop before the saved start time and reject live,
final, suspended, postponed and cancelled games. A later start-time change
does not reopen a record that already reached its original cutoff. The latest
valid pregame probability, price, line and tier remain frozen.

Accuracy and calibration include only the configured season and rows with a
timezone-aware stored-snapshot timestamp strictly before first pitch. Legacy
history remains intact; excluded records are counted in report `scope` fields.
Source final scores remain usable for settling actual user wagers, independently
of whether a historical model prediction can be trusted.

On the inspected commit `14105541cffdeec4db69218fef21835d952fcc90`, 335 of 360
graded game forecasts fail this pregame test. The remaining 25 have 13 correct
winners. The previous 66.94% headline is not a valid pregame benchmark. Only one
of the clean games has an independent raw probability snapshot, so no confidence
recalibration is justified. Historical forecasts were not reconstructed or
rewritten from later data. This repair does not claim a proven gain in future
prediction accuracy.

Validation: `python -m tests.test_pipeline` and
`python -m unittest tests.test_prediction_freeze`. The build workflow runs both.
