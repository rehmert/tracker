# PK What-if Protocol Builder

Adds a recurring hypothetical protocol builder to the PK Simulator. Specify the compound, start date/time, interval in days, duration, and weekly dose escalation stages. Preview the modeled exposure without saving; optionally save future doses as an existing editable PK scenario. No actual protocol, dose log, or inventory modifications.

Install small patch in /opt/tracker using unzip -o; restart tracker.service. No database migration.

Note: Only future planned doses are saved to the PK scenario. The schedule rules themselves are not saved as editable recurring rules; edit individual saved scenario doses instead. Modeling is exploratory and not a clinical dosing recommendation.
