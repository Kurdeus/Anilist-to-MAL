import requests, json, webbrowser


f = open('config.json')
data = json.load(f)
username, ANICLIENT, ANISECRET, REDIRECT_URL = data['username'], data['aniclient'], data['anisecret'], data['redirectUrl']
variables = {'username': username,'type': 'ANIME'}

def convertAnilistDataToXML(data):
  output = ''''''
  user_total_anime = 0
  user_total_watching = 0
  user_total_completed = 0
  user_total_onhold = 0
  user_total_dropped = 0
  user_total_plantowatch = 0
  data = data['data']['MediaListCollection']['lists']
  for x in range(0, len(data)):
    for item in data[x]['entries']:
      s = str(item['status'])
      # print(s)
      if s == "PLANNING":
        if variables['type'] == 'ANIME':
          s = "Plan to Watch"
        else:
          s = "Plan to Read"
        user_total_plantowatch += 1
      elif s == "DROPPED":
        s = "Dropped"
        user_total_dropped += 1
      elif s == "CURRENT":
        if variables['type'] == 'ANIME':
          s = "Watching"
        else:
          s = "Reading"
        user_total_watching += 1
      elif s == "PAUSED":
        s = "On-Hold"
        user_total_onhold += 1
      elif "completed" in s.lower():
        s = "Completed"
        user_total_completed += 1
      if item['startedAt']["year"] != None:
        sdate = "{}-{}-{}".format(str(item['startedAt']["year"]), str(item['startedAt']['month']), str(item['startedAt']['day']))
      else:
        sdate = "0000-00-00"
      if item['completedAt']["year"] != None:
        edate = "{}-{}-{}".format(str(item['completedAt']["year"]), str(item['completedAt']['month']), str(item['completedAt']['day']))
      else:
        edate = "0000-00-00"
      animeItem = ''
      animeItem += '        <anime>\n'
      animeItem += '          <series_animedb_id>' + str(item['media']['idMal']) + '</series_animedb_id>\n'
      animeItem += '          <series_episodes>' + str(item['media']['episodes']) + '</series_episodes>\n'
      animeItem += '          <my_watched_episodes>' + str(item['progress']) + '</my_watched_episodes>\n'
      animeItem += '          <my_score>' + str(item['score']) + '</my_score>\n'
      animeItem += '          <my_status>' + s + '</my_status>\n'
      animeItem += '          <my_start_date>'+ sdate + '</my_start_date>\n'
      animeItem += '          <my_finish_date>'+ edate + '</my_finish_date>\n'
      animeItem += '          <my_times_watched>' + str(item['repeat']) + '</my_times_watched>\n'
      animeItem += '          <update_on_import>1</update_on_import>\n'
      animeItem += '        </anime>\n\n'

      output += animeItem
      user_total_anime += 1


  outputStart = '''<?xml version="1.0" encoding="UTF-8" ?>
    <!--
     Created by XML Export feature at MyAnimeList.net
     Programmed by Xinil
     Last updated 5/27/2008
    -->

    <myanimelist>

      <myinfo>
        <user_id>123456</user_id>
        <user_name>''' + variables['username'] + '''</user_name>
        <user_export_type>1</user_export_type>
        <user_total_anime>''' + str(user_total_anime) + '''</user_total_anime>
        <user_total_watching>''' + str(user_total_watching) + '''</user_total_watching>
        <user_total_completed>''' + str(user_total_completed) + '''</user_total_completed>
        <user_total_onhold>''' + str(user_total_onhold) + '''</user_total_onhold>
        <user_total_dropped>''' + str(user_total_dropped) + '''</user_total_dropped>
        <user_total_plantowatch>''' + str(user_total_plantowatch) + '''</user_total_plantowatch>
      </myinfo>

'''
  output = outputStart + output + '      </myanimelist>'
  f = open("MAL.xml", 'w')
  f.write(output)
  f.close()
  return




def request_code():
    # Get OAuth and Access Token
    url = f"https://anilist.co/api/v2/oauth/authorize?client_id={ANICLIENT}&redirect_uri={REDIRECT_URL}&response_type=code"
    webbrowser.open(url)
    code = input("Paste your token code here (Copied from Anilist webpage result): ")
    return code




def request_token():
    body = {
        'grant_type': 'authorization_code',
        'client_id': ANICLIENT,
        'client_secret': ANISECRET,
        'redirect_uri': REDIRECT_URL,
        'code': request_code()
    }
    try:
        accessToken = requests.post("https://anilist.co/api/v2/oauth/token", json=body).json().get("access_token")
        #logger("Access Token: [" + accessToken + "]")
    except:
        accessToken = None
    return accessToken



def main():
  query = '''
    query ($username: String, $type: MediaType) {
    MediaListCollection (userName: $username, type: $type) { 
        lists {
            status
            entries
            {
                status
                completedAt { year month day }
                startedAt { year month day }
                progress
                repeat
                progressVolumes
                score(format: POINT_10)
                private
                media
                {
                    id
                    idMal
                    season
                    seasonYear
                    format
                    source
                    episodes
                    chapters
                    volumes
                    title
                    {
                        english
                        romaji
                    }
                    description
                    coverImage { medium }
                    synonyms
                    isAdult
                }
            }
        }
    }
    }
    '''
  response = requests.post('https://graphql.anilist.co', 
                           json={'query': query, 'variables': variables}, 
                           headers={"Authorization": "Bearer {}".format(request_token())})
  jsonData = response.json()
  convertAnilistDataToXML(jsonData)
  return



main()