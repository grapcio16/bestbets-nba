TEAM_MAP = {
 'Atlanta Hawks':'ATL','Boston Celtics':'BOS','Brooklyn Nets':'BKN',
 'Charlotte Hornets':'CHA','Chicago Bulls':'CHI','Cleveland Cavaliers':'CLE',
 'Dallas Mavericks':'DAL','Denver Nuggets':'DEN','Detroit Pistons':'DET',
 'Golden State Warriors':'GSW','Houston Rockets':'HOU','Indiana Pacers':'IND',
 'LA Clippers':'LAC','Los Angeles Clippers':'LAC','Los Angeles Lakers':'LAL',
 'Memphis Grizzlies':'MEM','Miami Heat':'MIA','Milwaukee Bucks':'MIL',
 'Minnesota Timberwolves':'MIN','New Orleans Pelicans':'NOP','New York Knicks':'NYK',
 'Oklahoma City Thunder':'OKC','Orlando Magic':'ORL','Philadelphia 76ers':'PHI',
 'Phoenix Suns':'PHX','Portland Trail Blazers':'POR','Sacramento Kings':'SAC',
 'San Antonio Spurs':'SAS','Toronto Raptors':'TOR','Utah Jazz':'UTA',
 'Washington Wizards':'WAS'
}
TEAM_FULL = {v:k for k,v in TEAM_MAP.items()}

def standardize_teams(df):
    if df is None or df.empty:return df
    x=df.copy();x.columns=[str(c).upper() for c in x.columns]
    if 'TEAM_ABBREVIATION' not in x:
        if 'TEAM_NAME' in x:x['TEAM_ABBREVIATION']=x['TEAM_NAME'].map(TEAM_MAP)
        else:x['TEAM_ABBREVIATION']=''
    return x
