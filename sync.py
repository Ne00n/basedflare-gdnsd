from pymongo import MongoClient
import subprocess, tldextract, os

with open('config.json', 'r') as f: config = json.load(f)

client = MongoClient() 
client = MongoClient(config['mongodb']) 

db = client['test']
collection = db['accounts']
cursor = collection.find({})

domains = {}
for user in cursor:
    for domain in user['domains']:
        ext = tldextract.extract(domain)
        if not ext.registered_domain in domains: domains[ext.registered_domain] = []
        if ext.subdomain: domains[ext.registered_domain].append(domain)

def gdnsdZone(domains):
        nameservers = config['nameservers'].split(",") 
        template = f'''$TTL 86400
@     SOA {nameservers[0]} admin. (
      1      ; serial
      7200   ; refresh
      30M    ; retry
      3D     ; expire
      900    ; ncache
)

@   NS	{nameservers[0]}.
@   NS	{nameservers[1]}.
'''
        for domain in domains: template += f"{domain}     30    DYNA    geoip!geo_www\n"
        return template

#update zones
gdnsdZonesDir = "/etc/gdnsd/zones"
files,current,reload = os.listdir(gdnsdZonesDir),[],False
for domain,subdomains in domains.items():
    zone = gdnsdZone(subdomains)
    with open(f"{gdnsdZonesDir}/{domain}", 'w') as out: out.write(zone)
    current.append(domain)
    reload = True

#domains removed from database
for file in files:
    if file not in current:
        os.remove(f"{gdnsdZonesDir}/{file}")
        reload = True

if reload: subprocess.run(["/usr/bin/sudo", "/usr/bin/gdnsdctl", "reload-zones"])