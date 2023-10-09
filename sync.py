from pymongo import MongoClient
import subprocess, tldextract

client = MongoClient() 
client = MongoClient("mongodb://localhost:27017/") 

db = client['test']
collection = db['accounts']
cursor = collection.find({})

domains = {}
for user in cursor:
    for domain in user['domains']:
        ext = tldextract.extract(domain)
        if not ext.registered_domain in domains: domains[ext.registered_domain] = []
        if ext.subdomain: domains[ext.registered_domain].append(domain)

#update zones
gdnsdZonesDir = "/etc/gdnsd/zones"
files,current,reload = os.listdir(gdnsdZonesDir),[],False
for domain,subdomains in domains.items():
    zone = ""
    with open(f"{gdnsdZonesDir}/{domain}", 'w') as out: out.write(zone)
    current.append(domain)
    reload = True

#domains removed from database
for file in files:
    if file not in current:
        os.remove(f"{gdnsdZonesDir}/{file}")
        reload = True

if reload: subprocess.run(["/usr/bin/sudo", "/usr/bin/gdnsdctl", "reload-zones"])