from gevent import monkey; monkey.patch_all()
import os
import sys
import time
import math
import functools
import random
import json

import redis
import gevent

if os.environ.get("REDISCLOUD_URL"):
    REDIS_URL = os.environ.get("REDISCLOUD_URL")
else:
    REDIS_URL = None
    print("No redis url!")
    sys.exit(1)
    
pool = redis.BlockingConnectionPool.from_url(REDIS_URL, max_connections=9)
redisConn = redis.Redis(connection_pool = pool)

GRID_SIZE = 64

# decorator
def actionRequire(*required_args):
    def decorator(func):
        @functools.wraps(func)
        def wrapper(*args, **kw):
            if 'action' in kw:
                action = kw['action']
            else:
                action = args[1]
            for r in required_args:
                if r not in action:
                    print("Error on input, need {}, get{}".format(r, action))
                    return False
            return func(*args, **kw)
        return wrapper
    return decorator

class Point:
    def __init__(self, x = 0, y = 0):
        self.x = x
        self.y = y
    def copy(self):
        return Point(self.x, self.y)
    def getDist(self, p):
        return ((p.x - self.x)**2 + (p.y-self.y)**2)**0.5
    def getAngle(self, p):
        return math.atan2(p.y-self.y, p.x-self.x)
    def getShift(self, angle, length):
        x = length*math.cos(angle) + self.x
        y = length*math.sin(angle) + self.y
        return Point(x, y)
    def __repr__(self):
        return "({}, {})".format(self.x, self.y)

class MapCell:
    def __init__(self, tile = 1):
        self.walkable = True
        self.tile = tile
    def getInfo(self):
        return {'tile':self.tile}

class Map:
    def __init__(self, height = 30, width = 30):
        self.height = height
        self.width = width
        self.data = [[MapCell(tile = i) for i in range(self.width)] for j in range(self.height)]
        self.gridSize = GRID_SIZE

    def collide(self, obj):
        if obj.pos.x - obj.width/2 < 0 or obj.pos.x + obj.width/2 > self.gridSize * self.width \
                or obj.pos.y - obj.height/2 < 0 or obj.pos.y + obj.height/2 > self.gridSize * self.height:
                    return True
        for i in range(int((obj.pos.x - obj.width/2)/self.gridSize), int((obj.pos.x + obj.width/2)/self.gridSize)+1):
            for j in range(int((obj.pos.y - obj.height/2)/self.gridSize), int((obj.pos.y + obj.height/2)/self.gridSize)+1):
                if self.data[j][i].walkable == False:
                    return True
        return False

    def getInfo(self):
        mapInfo = {}
        tileInfo = []
        for row in self.data:
            rowInfo = []
            for mapCell in row:
                rowInfo.append(mapCell.tile)
            tileInfo.append(rowInfo)
        mapInfo['tile'] = tileInfo

        return mapInfo
    
    def getRandomWalkableCoord(self):
        while True:
            i = random.randrange(0, self.height)
            j = random.randrange(0, self.width)
            if self.data[i][j].walkable:
                return (j*self.gridSize + self.gridSize/2, i*self.gridSize + self.gridSize/2)
    
    def loadJson(self, fileName):
        with open(fileName) as f:
            jsonData = json.load(f)
            layer = jsonData['layers'][0]['data']
            for i in range(self.height):
                for j in range(self.width):
                    tileId = layer[i*self.width + j]
                    if tileId > 100:
                        self.data[i][j].walkable = False
                    else:
                        self.data[i][j].walkable = True

class GameObject:
    def __init__(self):
        self.id = 1
        self.pos = Point()
        self.moveDestination = Point()
        self.moveAngle = 0
        self.speed = 0
        self.width = 64
        self.height = 64

    def setPos(self, px, y = 0):
        if type(px) == Point:
            self.pos = px.copy()
        else:
            self.pos.x = px
            self.pos.y = y

    def setMove(self, px, y, moveSpeed):
        if type(px) == Point:
            self.moveDestination = p.copy()
        else:
            self.moveDestination = Point(px, y)
        self.moveAngle = self.pos.getAngle(self.moveDestination)
        self.speed = moveSpeed
    
    def setAngle(self, angle):
        self.moveAngle = angle

    def setSpeed(self, speed):
        self.speed = speed
    
    def move(self, time, m):
        if time != 0:
            newPos = self.pos.getShift(self.moveAngle, self.speed*time)
            oldPos = self.pos.copy()
            self.pos = newPos
            # If already arrived at position or collide, stop
            if (self.pos.getDist(self.moveDestination) > oldPos.getDist(self.moveDestination) and type(self) == Player) or \
                    m.collide(self):
                self.pos = oldPos
                self.speed = 0

class Player(GameObject):
    def __init__(self):
        GameObject.__init__(self)
        self.name = ""
        self.moveSpeed = 100
        self.width = 40
        self.height = 40
        self.id = 0
        self.hp = 100
        self.lastAction = None
        self.dead = False
        self.kill = 0
        self.death = 0

    def getInfo(self):
        ret = {}
        ret['x'] = self.pos.x
        ret['y'] = self.pos.y
        ret['hp'] = self.hp
        ret['name'] = self.name
        ret['angle'] = self.moveAngle
        ret['speed'] = self.speed
        ret['id'] = self.id
        ret['dead'] = self.dead
        ret['kill'] = self.kill
        ret['death'] = self.death

        return ret

    def move(self, time, m):
        if time != 0:
            newPos = self.pos.getShift(self.moveAngle, self.speed*time)
            oldPos = self.pos.copy()
            self.pos = newPos
            # If already arrived at position or collide, stop
            if (self.pos.getDist(self.moveDestination) > oldPos.getDist(self.moveDestination)) or \
                    m.collide(self):
                self.pos = oldPos
                self.speed = 0
                return False
            return True

        return False

class Bullet(GameObject):
    def __init__(self):
        GameObject.__init__(self)
        self.speed = 200
        self.width = 10
        self.height = 10
    
    def getInfo(self):
        ret = {}
        ret['x'] = self.pos.x
        ret['y'] = self.pos.y
        ret['angle'] = self.moveAngle
        ret['speed'] = self.speed
        ret['id'] = self.id

        return ret

    def move(self, time, m):
        if time != 0:
            newPos = self.pos.getShift(self.moveAngle, self.speed*time)
            oldPos = self.pos.copy()
            self.pos = newPos
            # If already arrived at position or collide, stop
            if m.collide(self):
                self.pos = oldPos
                self.speed = 0
                return False
            return True
        return False

class Item(GameObject):
    def __init__(self, itemType = None):
        GameObject.__init__(self)
        if itemType == None:
            self.itemType = random.choice(['health'])
        else:
            self.itemType = itemType
    
    def getInfo(self):
        ret = {}
        ret['id'] = self.id
        ret['x'] = self.pos.x
        ret['y'] = self.pos.y
        ret['itemType'] = self.itemType
        
        return ret

    def buff(self, player):
        if self.itemType == 'health':
            player.hp = min(player.hp + 20, 100)

class Game:
    def __init__(self):
        self.width = 30
        self.height = 30
        self.gridSize = GRID_SIZE
        self.redisConn = RedisConn()
        self.framePerSec = 10
        self.gameMap = Map(height = self.height, width = self.width)
        self.gameMap.loadJson('./map.json')
        self.currFrame = 0
        self.startTime = 0
        self.players = []
        self.playerId = 1
        self.bullets = []
        self.bulletId = 1
        self.items = []
        self.itemId = 1
        self.eventQueue = []

    def addPlayer(self, p):
        self.players.append(p)

    def addBullet(self, b):
        self.bullets.append(b)

    def joinGame(self, channel, name):
        p = self.getPlayerByChannel(channel)
        if p:
            if p.dead:
                p.hp = 100
                p.dead = False
            return p.id
        p = Player()
        x, y = self.gameMap.getRandomWalkableCoord()
        p.setPos(x, y)
        p.speed = 50
        p.channel = channel
        p.id = self.playerId
        p.name = name
        p.lastAction = time.time()
        self.playerId += 1
        self.addPlayer(p)
        return p.id

    def getPlayerById(self, id):
        for p in self.players:
            if p.id == id:
                return p
        return None
    
    def getPlayerByChannel(self, channel):
        for p in self.players:
            if p.channel == channel:
                return p
        return None

    def newBullet(self, pos, speed, angle, player):
        if player != None and not player.dead:
            bullet = Bullet()
            bullet.setPos(pos)
            bullet.setSpeed(speed)
            bullet.setAngle(angle)
            bullet.id = self.bulletId
            bullet.player = player.id
            self.bulletId += 1
            self.addBullet(bullet)

    def updatePlayers(self):
        for player in self.players:
            player.move(1.0/self.framePerSec, self.gameMap)

    def updateBullets(self):
        newBullets = []
        for bullet in self.bullets:
            if bullet.move(1.0/self.framePerSec, self.gameMap):
                newBullets.append(bullet)
        self.bullets = newBullets

    def generateItem(self):
        x, y = self.gameMap.getRandomWalkableCoord()
        item = Item()
        item.id = self.itemId
        item.setPos(x, y)
        self.itemId += 1
        self.items.append(item)

    def updateFrame(self):
        self.updatePlayers()
        self.updateBullets()
        self.checkHit()
        if len(self.items) < 5*len(self.players) and random.uniform(0, 1) < 0.005 * len(self.players):
            self.generateItem()
        self.currFrame += 1

    def getDynamicGameInfo(self):
        info = {}
        info['infoType'] = 'dynamicGameInfo'
        playerInfo = []
        bulletInfo = []
        itemInfo   = []
        for player in self.players:
            playerInfo.append(player.getInfo())
        for bullet in self.bullets:
            bulletInfo.append(bullet.getInfo())
        for item in self.items:
            itemInfo.append(item.getInfo())
        info['players'] = playerInfo
        info['bullets'] = bulletInfo
        info['items']   = itemInfo
        info['timestamp'] = self.currFrame / self.framePerSec

        return info

    def getStaticMapInfo(self):
        info = {}
        info['infoType'] = 'staticMapInfo'
        info['map'] = self.gameMap.getInfo()

        return info

    # Parse Actions
    def doActions(self, actions):
        for action in actions:
            actionType = action['actionType']
            if actionType == 'move':
                if 'player' in action:
                    player = self.getPlayerById(action['player'])
                    if player and not player.dead:
                        player.lastAction = time.time()
                        player.setMove(action['x'], action['y'], player.moveSpeed)
            elif actionType == 'shoot':
                self.actionShoot(action)

            elif actionType == 'join':
                self.actionJoin(action)

            elif actionType == 'leave':
                self.actionLeave(action)
    
    @actionRequire("player", "x", "y")
    def actionShoot(self, action):
        player = self.getPlayerById(action['player'])
        if player and not player.dead:
            player.lastAction = time.time()
            angle = player.pos.getAngle(Point(action['x'], action['y']))
            pos = player.pos.getShift(angle, player.width)
            player.setSpeed(0)
            player.setAngle(angle)
            self.newBullet(pos = pos, angle = angle, player = player, speed = 200)

    @actionRequire("channel", "name")
    def actionJoin(self, action):
        channel = action['channel']
        id = self.joinGame(action['channel'], action['name'])
        self.redisConn.publishJoin(channel, id)

    @actionRequire("channel")
    def actionLeave(self, action):
        channel = action['channel']
        for i in range(len(self.players)):
            if self.players[i].channel == channel:
                self.players.pop(i)
                break

    def checkHit(self):
        newBullets = []
        newPlayers = []
        newItems   = []
        for b in self.bullets:
            bulletHit = False
            for p in self.players:
                if not p.dead and b.player != p.id and p.pos.getDist(b.pos) < p.width + b.width:
                    p.hp -= 10
                    bulletHit = True
                    self.eventQueue.append({'eventType':'bulletHit', 'player':p.id})
                    if p.hp <= 0 and p.dead == False:
                        atkPlayer = self.getPlayerById(b.player)
                        if atkPlayer:
                            atkPlayer.kill += 1
                        p.dead = True
                        p.death += 1
            if not bulletHit:
                newBullets.append(b)

        # Check for items
        for item in self.items:
            itemHit = False
            for p in self.players:
                if not p.dead and p.pos.getDist(item.pos) < p.width:
                    item.buff(p)
                    itemHit = True
            if not itemHit:
                newItems.append(item)

        # Get rid of inactive players
        for p in self.players:
            if p.lastAction >= time.time() - 60:
                newPlayers.append(p)

        self.players = newPlayers
        self.bullets = newBullets
        self.items   = newItems

    def run(self):
        self.startTime = time.time()
        while True:
            currTime = time.time()
            while currTime > self.startTime + self.currFrame*(1/self.framePerSec):
                self.updateFrame()
            actions = self.redisConn.getActions()
            self.doActions(actions)
            
            self.redisConn.setDynamicGameInfo(self.getDynamicGameInfo())
            self.redisConn.setStaticMapInfo(self.getStaticMapInfo())
            for event in self.eventQueue:
                self.redisConn.publishEvent(event)
            self.eventQueue = []



class RedisConn:
    def setDynamicGameInfo(self, info):
        gevent.spawn(redisConn.set, "dynamicGameInfo", json.dumps(info), ex=3600)

    def setStaticMapInfo(self, info):
        gevent.spawn(redisConn.set, "staticMapInfo", json.dumps(info), ex=3600)

    def publishEvent(self, event):
        gevent.spawn(redisConn.publish, 'events', json.dumps({'infoType':'event', 'event':event}))

    def publishJoin(self, channel, id):
        gevent.spawn(redisConn.publish, 'events', json.dumps({'infoType':'joinInfo', 'channel':channel, 'id': id}))


    def getActions(self):
        pipe = redisConn.pipeline()
        pipe.lrange("actionQueue", 0, -1)
        pipe.delete("actionQueue")
        result = pipe.execute()
        ret = []
        if result and result[0]:
            for r in result[0]:
                ret.append(json.loads(r))
        return ret

if __name__ == '__main__':
    g = Game()
    g.run()
