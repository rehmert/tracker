MULTIPLE COAS PER VIAL / KIT — TRACKER v2.3

Install on the current working Tracker (with Eastern display and projection exclusions).
Stop the service and make a consistent backup before installing.

sudo systemctl stop tracker
sudo tar -czf /root/tracker-before-multicoa-$(date +%Y%m%d-%H%M%S).tar.gz -C /opt tracker
cd /opt/tracker
sudo unzip -o /path/to/tracker-multiple-coas-small-patch.zip -d /opt/tracker
sudo chown -R tracker:tracker /opt/tracker/app
sudo systemctl start tracker
sudo systemctl status tracker --no-pager -l

The application creates a new coa_vial_links association table at startup and seeds it from existing vial.coa_id values. It preserves the legacy field and all historical COA files. No existing COA links are removed.

Vial detail -> Link an existing COA -> This vial / This half-kit / Entire kit.
A half-kit is determined by vial ID ordering within the same purchase+kit_ref, with the selected vial deciding the half.
Uploading a new COA adds a link instead of replacing the previous COA.
When Use COA content is enabled, content is the equal-weight arithmetic mean of all linked COAs with positive compatible content, normalized to base units first. COAs without a reported content are excluded from the mean.
Unlinking removes only the selected vial/COA link; deleting a COA deletes the certificate globally.

Important: If you tested different samples from a kit and wish to assign each sample to only one half, use the half-kit action rather than entire kit.
