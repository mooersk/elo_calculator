import sqlite3
import time

#see https://en.wikipedia.org/wiki/Elo_rating_system
#set model sensitivity parameters
FIDE_constant = int(400)
K = int(32)
default_elo = int(1000)

#open database connection
conn = sqlite3.connect('elo.sqlite')
cur = conn.cursor()

cur.execute('''CREATE TABLE IF NOT EXISTS player
    (player_id INTEGER NOT NULL PRIMARY KEY AUTOINCREMENT UNIQUE,
    player_name TEXT UNIQUE, player_elo INTEGER)''')

cur.execute('''CREATE TABLE IF NOT EXISTS deck
    (deck_id INTEGER NOT NULL PRIMARY KEY AUTOINCREMENT UNIQUE, player_id INTEGER,
    player_name TEXT, deck_name TEXT, old_elo INTEGER, new_elo INTEGER)''')

cur.execute('''CREATE TABLE IF NOT EXISTS game
    (game_id INTEGER NOT NULL PRIMARY KEY AUTOINCREMENT UNIQUE,
    date DATE, deck_ids TEXT, winner_id INTEGER)''')

cur.execute('''CREATE TABLE IF NOT EXISTS game_member
    (deck_id INTEGER, game_id INTEGER, old_elo INTEGER, new_elo INTEGER,
    PRIMARY KEY (deck_id, game_id))''')

#Ask user to input player data. Choose good names!
#The player name and deck name will be used to look up ELO in future database checks
players = []
decks = []
ratings = []
player_ratings = []
try:
    players = str(input("Players [John, Jane, etc]: ")).split(",")
    decks = str(input("Decks [Mogis, Krav, etc]: ")).split(",")
    winner = int(input("Which Player Won? [e.g. 1, 2, or 3]: ")) - 1
    players = [item.strip() for item in players]
    decks = [item.strip() for item in decks]

except:
    print("Error in input data")
    quit()
print('')

#check that the number of players and decks is the same
if (len(players) != len(decks)) or (winner >= len(players)):
    print("Lists not of equal length! Start over")
    quit()

#check if deck exists. If so, pull existing rating. ANON decks get default rating.
for x in range(len(players)):
    #player elo
    cur.execute('SELECT player_elo FROM player WHERE player_name = ? ', (players[x], ))
    try: player_elo = cur.fetchone()[0]
    except: player_elo = None

    if (player_elo is None) or (players[x] == 'ANON'):
        player_ratings.append(default_elo)
    else:
        player_ratings.append(player_elo)

    #deck elo
    cur.execute('SELECT new_elo FROM deck WHERE player_name = ? AND deck_name = ? ', (players[x], decks[x]))
    try: new_elo = cur.fetchone()[0]
    except: new_elo = None

    if (new_elo is None) or (players[x] == 'ANON'):
        ratings.append(default_elo)
    else:
        ratings.append(new_elo)

#compute q, e, s, and new rating
#see https://en.wikipedia.org/wiki/Elo_rating_system
def calc_elo(ratings, winner, FIDE_constant: int, K: int):
    q = []
    e = []
    newratings = []
    s = [0] * len(ratings)
    s[winner] = 1

    for x in range(len(ratings)):
        q.append(10.**(ratings[x]/FIDE_constant))

    for x in range(len(ratings)):
        e.append(q[x] / sum(q))
        newratings.append(round(ratings[x] + K*(s[x]-e[x]) ))

    return newratings, s

newratings, s = calc_elo(ratings, winner, FIDE_constant, K)
player_ratings = calc_elo(player_ratings, winner, FIDE_constant, K)[0]

#print results
print("==============================")
print("Players:", players)
print("Decks:", decks)
print("Winner:", s)
print("Old Ratings:", ratings)
print("New Ratings:", newratings)
print("Player Elo:", player_ratings)
print("==============================\n")

#check if we want to commit to memory
commit = str(input("Commit to memory? (Yes/No): "))
if commit == "Yes" or commit == "yes":
    #create new game entry
    date = time.strftime('%Y-%m-%d %H:%M:%S')
    cur.execute('''INSERT OR IGNORE INTO game (date) VALUES (?)''', (date,) )
    cur.execute('SELECT game_id FROM game WHERE date = ? ', (date, ))
    game_id = cur.fetchone()[0]

    #update player and deck records
    deck_ids = []
    for x in range(len(players)):
        player_name = players[x]
        deck_name = decks[x]
        old_rating = ratings[x]
        new_rating = newratings[x]
        player_rating = player_ratings[x]
        winner = s[x]

        #insert or replace player elo
        cur.execute('SELECT player_id FROM player WHERE player_name = ?', (player_name, ))
        try: player_id = cur.fetchone()[0]
        except: player_id = None

        cur.execute('''INSERT OR REPLACE INTO player (player_id, player_name, player_elo)
            VALUES (?, ?, ?)''', (player_id, player_name, player_rating) )
        cur.execute('SELECT player_id FROM player WHERE player_name = ?', (player_name, ))
        player_id = cur.fetchone()[0]

        #insert or replace deck elo
        cur.execute('SELECT deck_id FROM deck WHERE player_name = ? AND deck_name = ?', (player_name, deck_name))
        try: deck_id = cur.fetchone()[0]
        except: deck_id = None

        cur.execute('''INSERT OR REPLACE INTO deck (deck_id, player_id, player_name, deck_name, old_elo, new_elo)
            VALUES (?, ?, ?, ?, ?, ? )''', (deck_id, player_id, player_name, deck_name, old_rating, new_rating ) )
        cur.execute('SELECT deck_id FROM deck WHERE player_name = ? AND deck_name = ? ', (player_name, deck_name))
        deck_id = cur.fetchone()[0]
        deck_ids.append(deck_id)

        if winner == 1:
            cur.execute('''UPDATE game
                SET winner_id = ? WHERE game_id = ? ''',
                (deck_id, game_id))

        cur.execute('''INSERT OR IGNORE INTO game_member
            (deck_id, game_id, old_elo, new_elo) VALUES (?, ?, ?, ?)''',
            (deck_id, game_id, old_rating, new_rating) )

        print((deck_id, player_name, deck_name, winner, old_rating, new_rating, player_rating, date))

    #now that we have created the game_id and all deck_ids, record the decks involved in the game
    cur.execute('''UPDATE game SET deck_ids = ? WHERE game_id = ? ''',
        (str(deck_ids), game_id))
    conn.commit()
    print('Database Update Completed\n')
print('')
