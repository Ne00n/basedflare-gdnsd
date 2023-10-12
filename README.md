# basedflare-gdnsd

```
useradd cdn -d /opt/basedflare-gdnsd -s /bin/bash
mkdir /opt/basedflare-gdnsd && chown -R cdn:cdn /opt/basedflare-gdnsd/ && cd /opt/;su cdn
git clone https://github.com/Ne00n/basedflare-gdnsd.git && cd basedflare-gdnsd
exit
apt-get install gdnsd sudo python3-pip -y
pip3 install tldextract pymongo redis
echo "cdn ALL=(ALL) NOPASSWD: /usr/bin/gdnsdctl reload-zones" >> /etc/sudoers.d/gdnsd
chgrp -R cdn /etc/gdnsd/ && chmod 775 -R /etc/gdnsd/
cp /opt/basedflare-gdnsd/cdnDNS.service /etc/systemd/system/ && systemctl enable cdnDNS && systemctl start cdnDNS
#you have to edit the config and download the .mmdb file to /etc/gdnsd/geopip/
cp config /etc/gdnsd/
systemctl restart gdnsd
```