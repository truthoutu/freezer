# Generate comprehensive URL lists for targets_registry.py

 = @{
    "Germany" = @{
        "Nurse" = @()
        "Doctor" = @()
        "Realtor" = @()
        "Lawyer" = @()
    }
    "Switzerland" = @{
        "Nurse" = @()
        "Doctor" = @()
        "Lawyer" = @()
    }
    "Australia" = @{
        "Nurse" = @()
        "Doctor" = @()
        "Realtor" = @()
        "Lawyer" = @()
    }
    "United States" = @{
        "Nurse" = @()
        "Realtor" = @()
        "Lawyer" = @()
    }
}

# Generate Germany URLs
 = @("bundesweit","berlin","hamburg","muenchen","koeln","frankfurt","stuttgart","duesseldorf","dortmund","essen","leipzig","bremen","dresden","hannover","nuernberg","duisburg","bochum","wuppertal","bielefeld","bonn","muenster","karlsruhe","mannheim","augsburg","wiesbaden","gelsenkirchen","mainz","braunschweig","chemnitz","kiel","aachen","halle","magdeburg","freiburg","krefeld","luebeck","rostock","erfurt","kassel","saarbruecken","wuerzburg","potsdam","heidelberg","regensburg","ingolstadt","mannheim","viersen","goettingen","ulm","bonn")

# Add German nurse URLs (100 URLs)
for (=0;  -lt 100; ++) {
     = [ % .Length]
    ["Germany"]["Nurse"] += "https://www.gelbenseiten.de/suche/pflegedienst/?page="
    ["Germany"]["Nurse"] += "https://www.dasoertliche.de/Themen/Krankenschwester+?page="
}

# Add German doctor URLs (100 URLs)
for (=0;  -lt 100; ++) {
     = [ % .Length]
    ["Germany"]["Doctor"] += "https://www.gelbenseiten.de/suche/aerzte/?page="
    ["Germany"]["Doctor"] += "https://www.dasoertliche.de/Themen/Arzt+?page="
}

# Add German realtor URLs (100 URLs)
for (=0;  -lt 100; ++) {
     = [ % .Length]
    ["Germany"]["Realtor"] += "https://www.gelbenseiten.de/suche/immobilienmakler/?page="
    ["Germany"]["Realtor"] += "https://www.dasoertliche.de/Themen/Immobilienmakler+?page="
}

# Add German lawyer URLs (100 URLs)
for (=0;  -lt 100; ++) {
     = [ % .Length]
    ["Germany"]["Lawyer"] += "https://www.gelbenseiten.de/suche/rechtsanwalt/?page="
    ["Germany"]["Lawyer"] += "https://www.dasoertliche.de/Themen/Rechtsanwalt+?page="
}

# Generate US URLs
 = @("NY","Los+Angeles","Chicago","Houston","Phoenix","Philadelphia","San+Antonio","San+Diego","Dallas","San+Jose","Austin","Jacksonville","Fort+Worth","Columbus","Charlotte","Indianapolis","San+Francisco","Seattle","Denver","Washington+DC","Nashville","Portland","Las+Vegas","Milwaukee","Albuquerque","Tucson","Fresno","Sacramento","Mesa","Atlanta","Kansas+City","Colorado+Springs","Raleigh","Omaha","Miami","Long+Beach","Virginia+Beach","Oakland","Minneapolis","Tulsa","Arlington","Tampa","New+Orleans","Cleveland","Bakersfield","Aurora","Anaheim","Honolulu","Riverside","Corpus+Christi","Lexington","Stockton","Cincinnati","Saint+Paul","Pittsburgh","St.+Louis","Greensboro","Toledo","Newark","Jersey+City","Plano","Lincoln","Orlando","Chandler","Laredo","Chula+Vista","Buffalo","Irving","Chesapeake","Gilbert","Fort+Wayne","Lubbock","Glendale","Hialeah","Garland","Scottsdale","Irving","Chesapeake","Richmond","Madison","Birmingham","Norfolk","Louisville","Akron","Simi+Valley","Fontana","Oxnard","Aurora","Moreno+Valley","Rochester","Fargo","Mobile","Little+Rock","Huntington+Beach","Glendale","Grand+Rapids","Salt+Lake+City","Tallahassee","Worcester","Knoxville","Brownsville","Overland+Park","Providence","Jackson","Garden+Grove","Oklahoma+City","Huntsville","Chattanooga","Fort+Lauderdale","Santa+Clarita","Tempe","Vancouver")

# Add US nurse URLs (100 URLs)
for (=0;  -lt 100; ++) {
     = [ % .Length]
    ["United States"]["Nurse"] += "https://www.yellowpages.com/search?search_terms=nurse&geo_location_terms=&page="
    ["United States"]["Nurse"] += "https://www.healthgrades.com/search?query=Nurse&location="
}

# Add US realtor URLs (100 URLs)
for (=0;  -lt 100; ++) {
     = [ % .Length]
    ["United States"]["Realtor"] += "https://www.yellowpages.com/search?search_terms=real+estate+agent&geo_location_terms=&page="
    ["United States"]["Realtor"] += "https://www.zillow.com/professionals/real-estate/"
}

# Add US lawyer URLs (100 URLs)
for (=0;  -lt 100; ++) {
     = [ % .Length]
    ["United States"]["Lawyer"] += "https://www.yellowpages.com/search?search_terms=lawyer&geo_location_terms=&page="
    ["United States"]["Lawyer"] += "https://www.avvo.com/search/lawyer/"
}

# Generate Australia URLs
 = @("Sydney","Melbourne","Brisbane","Perth","Adelaide","Gold+Coast","Canberra","Newcastle","Wollongong","Logan+City","Geelong","Hobart","Townsville","Cairns","Darwin","Toowoomba","Ballarat","Bendigo","Albury","Launceston","Mackay","Rockhampton","Bunbury","Coffs+Harbour","Bundaberg","Wagga+Wagga","Hervey+Bay","Mildura","Gladstone","Shepparton","Sunshine+Coast","Port+Macquarie","Devonport","Tamworth","Orange","Lismore","Nowra","Bairnsdale","Gippsland","Traralgon")

for (=0;  -lt 100; ++) {
     = [ % .Length]
    ["Australia"]["Nurse"] += "https://www.yellowpages.com.au/search/findings?text=nurse+&page="
    ["Australia"]["Doctor"] += "https://www.yellowpages.com.au/search/findings?text=doctor+&page="
    ["Australia"]["Realtor"] += "https://www.yellowpages.com.au/search/findings?text=real+estate+agent+&page="
    ["Australia"]["Lawyer"] += "https://www.yellowpages.com.au/search/findings?text=solicitor+&page="
}

# Generate Switzerland URLs
 = @("Zuerich","Genf","Basel","Lausanne","Bern","Winterthur","Luzern","St.Gallen","Lugano","Biel","Thun","Koeniz","La+Chaux-de-Fonds","Schaffhausen","Fribourg","Vernier","Neuenburg","Chur","Sion","Emmen","Aarau","Uster","Zug","Freiamt","Kriens","Rapperswil","Baar","Wettingen","Baden","Horgen")

for (=0;  -lt 100; ++) {
     = [ % .Length]
    ["Switzerland"]["Nurse"] += "https://tel.search.ch/?was=Infirmiere&wo=&page="
    ["Switzerland"]["Doctor"] += "https://tel.search.ch/?was=Arzt&wo=&page="
    ["Switzerland"]["Lawyer"] += "https://tel.search.ch/?was=Avocat&wo=&page="
}

# Output as Python dictionary
Write-Output "TARGET_SOURCES = {"
foreach ( in .Keys | Sort-Object) {
    Write-Output "    "": {"
    foreach ( in [].Keys | Sort-Object) {
        Write-Output "        "": ["
         = [][]
        for (=0;  -lt .Count; ++) {
            if ( -lt .Count - 1) {
                Write-Output "            "","
            } else {
                Write-Output "            """
            }
        }
        Write-Output "        ],"
    }
    Write-Output "        "default": [""]"
    Write-Output "    },"
}
Write-Output "}"

