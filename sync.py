from pymongo import MongoClient
import subprocess, tldextract, hashlib, redis, json, time, os

with open('config.json', 'r') as f: config = json.load(f)
client = MongoClient(config['mongodb'])

pool = redis.ConnectionPool(host='localhost', port=6379, db=0)
redis = redis.Redis(connection_pool=pool)

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
            if ext.subdomain: domains[ext.registered_domain].append({"record":ext.subdomain,"type":"A"})

    keys = redis.keys('dns:*')
    for key in keys:
        domain = key.decode("utf-8").split(":")[1][:-1]
        data = redis.hgetall(key)
        for row,details in data.items():
            details = details.decode("utf-8")
            row = row.decode("utf-8")
            details = json.loads(details)
            if row == "@": continue
            domains[domain].append({"record":row,"type":"TXT","content":details['txt'][0]['text']})

    def gdnsdZone(domain,domains):
            nameservers = config['nameservers'].split(",") 
            template = f'''$TTL 86400
@     SOA {nameservers[0]}. admin.{domain}. (
    1      ; serial
    7200   ; refresh
    30M    ; retry
    3D     ; expire
    900    ; ncache
)

@   NS	{nameservers[0]}.
@   NS	{nameservers[1]}.
'''
            for row in domains: 
                if row['type'] == "TXT":
                    template += f"{row['record']}     60    TXT    \"{row['content']}\"\n"
                else:
                    template += f"{row['record']}     30    DYNA    geoip!geo_www\n"
            return template

    #update zones
    gdnsdZonesDir = "/etc/gdnsd/zones"
    prefix = "basedflare"
    current,reload = [],False

    for domain,subdomains in domains.items():
        subdomains.append({"record":"@","type":"A"})
        zone = gdnsdZone(domain,subdomains)
        current.append(f"{prefix}{domain}")
        currentZoneHash = hashlib.sha256(json.dumps(subdomains, sort_keys=True).encode('utf-8')).hexdigest()
        if not domain in cache: 
            cache[domain] = currentZoneHash
            reload = True
        if currentZoneHash != cache[domain]: 
            cache[domain] = currentZoneHash
            reload = True
        if reload:
            with open(f"{gdnsdZonesDir}/{prefix}{domain}", 'w') as out: out.write(zone)

    files = os.listdir(gdnsdZonesDir)
    #domains removed from database
    for file in files:
        if file not in current and "baseflare" in file:
            os.remove(f"{gdnsdZonesDir}/{file}")
            reload = True

    if reload: subprocess.run(["/usr/bin/sudo", "/usr/bin/gdnsdctl", "reload-zones"])
    reload = False
    time.sleep(1)