#!/usr/bin/env sh
cd /opt/tracker
sudo -u tracker git log --oneline -10            # find the last good commit
#sudo -u tracker git reset --hard <commit>
#sudo systemctl restart tracker
