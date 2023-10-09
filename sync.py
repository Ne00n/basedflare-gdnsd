from pymongo import MongoClient
import subprocess, tldextract, hashlib, json, time, os

with open('config.json', 'r') as f: config = json.load(f)
client = MongoClient(config['mongodb']) 

cache = {}
while True:
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
    current,reload = [],False

    for domain,subdomains in domains.items():
        subdomains.append(domain)
        zone = gdnsdZone(subdomains)
        current.append(domain)
        currentZoneHash = hashlib.sha256(' '.join(subdomains).encode('utf-8')).hexdigest()
        if not domain in cache: 
            cache[domain] = currentZoneHash
            reload = True
        if currentZoneHash != cache[domain]: 
            cache[domain] = currentZoneHash
            reload = True
        if reload:
            with open(f"{gdnsdZonesDir}/{domain}", 'w') as out: out.write(zone)

    files = os.listdir(gdnsdZonesDir)
    #domains removed from database
    for file in files:
        if file not in current:
            os.remove(f"{gdnsdZonesDir}/{file}")
            reload = True

    if reload: subprocess.run(["/usr/bin/sudo", "/usr/bin/gdnsdctl", "reload-zones"])
    reload = False
    time.sleep(1)