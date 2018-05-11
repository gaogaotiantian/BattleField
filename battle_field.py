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
    
pool = redis.BlockingConnectionPool.from_url(REDIS_URL, max_connections=4)
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

class Weapon:
    def __init__(self):
        self.name = ""
        self.gap  = 2
        self.damage = 5
        self.size = 1
        self.speed = 200
        self.lastFire = 0
        self.length = 300
        self.weight = 0
        self.possibleFeatures = set(["bounce", "penetrate", "zigzag", "variantSpeed", "doubleLength"])
        self.features = set()

    def addFeature(self, feature):
        self.features.add(feature)

    def fire(self, pos, angle, player, currTime, id, checkGap = True):
        if (not checkGap) or currTime - self.lastFire > self.gap:
            b = Bullet()
            b.setPos(pos)
            b.setSpeed(self.speed)
            b.setAngle(angle)
            b.id = id
            b.damage = self.damage
            b.player = player.id
            b.width = self.size
            b.height = self.size
            b.length = self.length
            for feature in self.features:
                b.features.add(feature)
            if b.hasFeature('doubleLength'):
                b.length *= 2
            self.lastFire = currTime
            return [b]
        return None

class WeaponBase(Weapon):
    def __init__(self):
        Weapon.__init__(self)
        self.name = 'base'
        self.weight = 5
        
class WeaponPistol(Weapon):
    def __init__(self):
        Weapon.__init__(self)
        self.name = 'german_pistol'
        self.gap = 1.5
        self.damage = 7
        self.size = 3
        self.weight = 5

class WeaponMp40(Weapon):
    def __init__(self):
        Weapon.__init__(self)
        self.name = 'mp_40'
        self.gap = 0.15
        self.damage = 10
        self.size = 4
        self.speed = 300
        self.length = 600
        self.weight = 10

class WeaponMp43(Weapon):
    def __init__(self):
        Weapon.__init__(self)
        self.name = 'mp_43'
        self.gap = 0.2
        self.damage = 20
        self.size = 6
        self.speed = 300
        self.weight = 20
        self.length = 700

class WeaponM1(Weapon):
    def __init__(self):
        Weapon.__init__(self)
        self.name = 'm1_carbine'
        self.gap = 3
        self.damage = 70
        self.size = 10
        self.speed = 450
        self.length = 1000
        self.weight = 25

class WeaponFg42(Weapon):
    def __init__(self):
        Weapon.__init__(self)
        self.name = 'fg_42'
        self.gap = 1.2
        self.damage = 10
        self.size = 4
        self.speed = 300
        self.length = 400
        self.weight = 20
    def fire(self, pos, angle, player, currTime, id):
        if currTime - self.lastFire > self.gap:
            ret = []
            for i in range(5):
                b = Weapon.fire(self, pos, angle+0.1*i-0.2, player, currTime, id, checkGap = False)
                if b:
                    id += 1
                    ret += b
            if len(ret) > 0:
                return ret
        return None

class WeaponAr(Weapon):
    def __init__(self):
        Weapon.__init__(self)
        self.name = 'ar'
        self.gap = 1
        self.damage = 15
        self.size = 5
        self.speed = 350
        self.length = 800

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
        self.weapon = WeaponBase()
        self.moveSpeed = 70
        self.width = 40
        self.height = 40
        self.id = 0
        self.hp = 100
        self.lastAction = None
        self.dead = False
        self.deadFrame = 0
        self.kill = 0
        self.death = 0

    def reborn(self, pos):
        self.pos = pos
        self.hp = 100
        self.moveSpeed = 70
        self.weapon = WeaponBase()
        self.dead = False

    def getInfo(self):
        ret = {}
        ret['x'] = self.pos.x
        ret['y'] = self.pos.y
        ret['hp'] = self.hp
        ret['name'] = self.name
        ret['angle'] = self.moveAngle
        ret['weapon'] = self.weapon.name
        ret['speed'] = self.speed
        ret['id'] = self.id
        ret['dead'] = self.dead
        ret['kill'] = self.kill
        ret['death'] = self.death

        return ret

    def move(self, time, m):
        if time != 0:
            newPos = self.pos.getShift(self.moveAngle, (self.speed - self.weapon.weight)*time)
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
        self.length = 100
        self.damage = 0
        self.features = set()
    
    def getInfo(self):
        ret = {}
        ret['x'] = self.pos.x
        ret['y'] = self.pos.y
        ret['size'] = self.width
        ret['angle'] = self.moveAngle
        ret['speed'] = self.speed - self.weapon.weight
        ret['id'] = self.id

        return ret

    def hasFeature(self, feature):
        return feature in self.features
    def move(self, time, m):
        if time != 0:
            newPos = self.pos.getShift(self.moveAngle, self.speed*time)
            oldPos = self.pos.copy()
            self.pos = newPos
            if self.hasFeature("zigzag"):
                self.moveAngle = self.moveAngle + 0.2 * random.uniform(-1,1)
            if self.hasFeature("variantSpeed"):
                self.speed = self.speed + 30 * random.uniform(-1,1)
            # If already arrived at position or collide, stop
            if not self.hasFeature('penetrate') and m.collide(self):
                if self.hasFeature('bounce') == True:
                    bouncePos = oldPos.copy()
                    self.pos = Point(newPos.x, oldPos.y)
                    bounceX = False
                    if m.collide(self):
                        bouncePos.y = 2*newPos.y - oldPos.y
                        bounceX = True
                    self.pos = Point(oldPos.x, newPos.y)
                    if m.collide(self):
                        if bounceX:
                            self.speed = 0
                            return False
                        bouncePos.x = 2*newPos.x - oldPos.x
                    self.pos = newPos
                    self.moveAngle = newPos.getAngle(bouncePos)
                    return True
                self.pos = oldPos
                self.speed = 0
                return False
            return True
        return False

class Item(GameObject):
    def __init__(self, itemType = None):
        GameObject.__init__(self)
        if itemType == None:
            self.itemType = random.choice(['health', 'german_pistol', 'mp_43', 'm1_carbine', 'mp_40', 'fg_42'])
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
        elif self.itemType == 'german_pistol':
            player.weapon = WeaponPistol()
        elif self.itemType == 'mp_43':
            player.weapon = WeaponMp43()
        elif self.itemType == 'm1_carbine':
            player.weapon = WeaponM1()
        elif self.itemType == 'mp_40':
            player.weapon = WeaponMp40()
        elif self.itemType == 'fg_42':
            player.weapon = WeaponFg42()
        elif self.itemType == 'random_weapon_buff':
            buff = random.choice(['bounce', 'penetrate', 'zigzag', 'variantSpeed', 'doubleLength'])
            player.weapon.addFeature(buff)
            

class Game:
    def __init__(self):
        self.width = 30
        self.height = 30
        self.gridSize = GRID_SIZE
        self.redisConn = RedisConn()
        self.framePerSec = 20
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
        x, y = self.gameMap.getRandomWalkableCoord()
        if p:
            if p.dead:
                p.reborn(Point(x,y))
            return p.id
        p = Player()
        p.setPos(x, y)
        p.speed = 70
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
            if not player.dead:
                player.move(1.0/self.framePerSec, self.gameMap)
            else:
                if self.currFrame - player.deadFrame > self.framePerSec:
                    x, y = self.gameMap.getRandomWalkableCoord()
                    player.reborn(Point(x, y))

    def updateBullets(self):
        newBullets = []
        for bullet in self.bullets:
            if bullet.move(1.0/self.framePerSec, self.gameMap):
                bullet.length -= bullet.speed / self.framePerSec
                if bullet.length > 0:
                    newBullets.append(bullet)
        self.bullets = newBullets

    def generateItem(self, pos = None, itemType = None):
        if pos == None:
            x, y = self.gameMap.getRandomWalkableCoord()
        else:
            x = pos.x
            y = pos.y
        item = Item(itemType)
        item.id = self.itemId
        item.setPos(x, y)
        self.itemId += 1
        self.items.append(item)

    def updateFrame(self):
        self.updatePlayers()
        self.updateBullets()
        self.checkHit()
        if len(self.items) < 5 + 2*len(self.players) and random.uniform(0, 1) < 0.005 + 0.001*len(self.players):
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
        player.lastAction = time.time()
        if player and not player.dead:
            angle = player.pos.getAngle(Point(action['x'], action['y']))
            pos = player.pos.getShift(angle, player.width)
            bList = player.weapon.fire(pos = pos, angle = angle, player = player, id = self.bulletId, currTime = self.currFrame / self.framePerSec)
            if bList != None:
                for b in bList:
                    player.setSpeed(0)
                    player.setAngle(angle)
                    self.addBullet(b)
                    self.bulletId += 1

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
                    p.hp -= b.damage
                    bulletHit = True
                    self.eventQueue.append({'eventType':'bulletHit', 'player':p.id})
                    if p.hp <= 0 and p.dead == False:
                        atkPlayer = self.getPlayerById(b.player)
                        if atkPlayer:
                            atkPlayer.kill += 1
                        p.dead = True
                        p.deadFrame = self.currFrame
                        p.death += 1
                        self.generateItem(pos = p.pos, itemType = 'random_weapon_buff')
                        
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
            if p.lastAction >= time.time() - 120:
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
