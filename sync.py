from pymongo import MongoClient
import subprocess, tldextract, hashlib, redis, json, time, os

with open('config.json', 'r') as f: config = json.load(f)
client = MongoClient(config['mongodb'])

pool = redis.ConnectionPool(host=config['redis']['host'], port=config['redis']['port'], db=0)
redis = redis.Redis(connection_pool=pool)

cache = {}
while True:

    keys = redis.keys('dns:*')
    domains = {}
    for key in keys:
        domain = key.decode("utf-8").split(":")[1][:-1]
        if not domain in domains: domains[domain] = []
        data = redis.hgetall(key)
        for row,details in data.items():
            details = details.decode("utf-8")
            row = row.decode("utf-8")
            details = json.loads(details)
            if row == "@": continue
            for type in details:
                for record in details[type]:
                    if type == "txt":
                        domains[domain].append({"record":row,"type":type,"ttl":record['ttl'],"content":record['text']})
                    else:
                        domains[domain].append({"record":row,"type":type,"ttl":record['ttl'],"content":record['ip']})

    db = client['test']
    collection = db['accounts']
    cursor = collection.find({})

    for user in cursor:
        for domain in user['domains']:
            ext = tldextract.extract(domain)
            if not ext.registered_domain in domains: domains[ext.registered_domain] = []
            if ext.subdomain: domains[ext.registered_domain].append({"record":ext.subdomain,"type":"DYNA"})

    def gdnsdZone(domain,domains):
            nameservers = config['nameservers'].split(",") 
            template = f'''$TTL 86400
@     SOA {nameservers[0]}. admin.{domain}. (
    {int(time.time())}  ; serial
    7200   ; refresh
    30M    ; retry
    3D     ; expire
    900    ; ncache
)

@   NS	{nameservers[0]}.
@   NS	{nameservers[1]}.
'''
            ignore = []
            for row in domains:
                if row['type'] == "txt":
                    template += f"{row['record']}     {row['ttl']}    TXT    \"{row['content']}\"\n"
                elif row['type'] == "DYNA":
                    if row['record'] in ignore: continue
                    template += f"{row['record']}     30    DYNA    geoip!geo_www\n"
                else:
                    template += f"{row['record']}     {row['ttl']}    {row['type'].upper()}   {row['content']}\n"
                    if row['type'] == "a": ignore.append(row['record'])
            return template

    #update zones
    gdnsdZonesDir = "/etc/gdnsd/zones"
    current,reload = [],False

    for domain,subdomains in domains.items():
        zone = gdnsdZone(domain,subdomains)
        current.append(domain)
        currentZoneHash = hashlib.sha256(json.dumps(subdomains, sort_keys=True).encode('utf-8')).hexdigest()
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
        if file not in current and file not in config['nameservers'].split(",")[0]:
            os.remove(f"{gdnsdZonesDir}/{file}")
            reload = True

    if reload: subprocess.run(["/usr/bin/sudo", "/usr/bin/gdnsdctl", "reload-zones"])
    reload = False
    time.sleep(1)