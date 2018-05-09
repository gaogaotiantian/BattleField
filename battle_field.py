import os
import sys
import time
import math

import redis
import random
import json

if os.environ.get("REDISCLOUD_URL"):
    REDIS_URL = os.environ.get("REDISCLOUD_URL")
else:
    REDIS_URL = None
    print("No redis url!")
    sys.exit(1)
    
pool = redis.BlockingConnectionPool.from_url(REDIS_URL, max_connections=9)
redisConn = redis.Redis(connection_pool = pool)
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
    def __init__(self):
        self.walkable = True
        self.tile = 1
    def getInfo(self):
        return {'tile':self.tile}

class Map:
    def __init__(self, height = 30, width = 30):
        self.height = height
        self.width = width
        self.data = [[MapCell() for i in range(self.width)] for j in range(self.height)]
        self.gridSize = 32

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



class GameObject:
    def __init__(self):
        self.id = 1
        self.pos = Point()
        self.moveDestination = Point()
        self.moveAngle = 0
        self.speed = 0
        self.width = 32
        self.height = 32

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
        self.moveSpeed = 50
        self.width = 48
        self.height = 48

    def getInfo(self):
        ret = {}
        ret['x'] = self.pos.x
        ret['y'] = self.pos.y
        ret['angle'] = self.moveAngle
        ret['speed'] = self.speed
        ret['id'] = self.id

        return ret

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

class Game:
    def __init__(self):
        self.width = 30
        self.height = 30
        self.gridSize = 32
        self.redisConn = RedisConn()
        self.framePerSec = 10
        self.gameMap = Map(height = self.height, width = self.width)
        self.currFrame = 0
        self.startTime = 0
        self.players = []
        self.playerId = 0
        self.bullets = []
        self.bulletId = 0

    def addPlayer(self, p):
        self.players.append(p)

    def addBullet(self, b):
        self.bullets.append(b)

    def updatePlayers(self):
        for player in self.players:
            player.move(1.0/self.framePerSec, self.gameMap)

    def updateBullets(self):
        for bullet in self.bullets:
            bullet.move(1.0/self.framePerSec, self.gameMap)

    def updateFrame(self):
        self.updatePlayers()
        self.updateBullets()
        self.currFrame += 1

    def getDynamicGameInfo(self):
        info = {}
        info['infoType'] = 'dynamicGameInfo'
        playerInfo = []
        bulletInfo = []
        for player in self.players:
            playerInfo.append(player.getInfo())
        for bullet in self.bullets:
            bulletInfo.append(bullet.getInfo())
        info['players'] = playerInfo
        info['bullets'] = bulletInfo
        info['timestamp'] = self.currFrame / self.framePerSec

        return info

    def getStaticMapInfo(self):
        info = {}
        info['infoType'] = 'staticMapInfo'
        info['map'] = self.gameMap.getInfo()

        return info

    def doActions(self, actions):
        for action in actions:
            actionType = action['actionType']
            if actionType == 'move':
                self.players[0].setMove(action['x'], action['y'], self.players[0].moveSpeed)
            if actionType == 'shoot':
                bullet = Bullet()
                bullet.setPos(self.players[0].pos)
                bullet.setSpeed(200)
                bullet.setAngle(self.players[0].moveAngle)
                bullet.id = self.bulletId
                self.bulletId += 1
                self.addBullet(bullet)


    def run(self):
        p = Player()
        p.setPos(400, 400)
        p.speed = 50
        self.addPlayer(p)
        self.startTime = time.time()
        while True:
            currTime = time.time()
            while currTime > self.startTime + self.currFrame*(1/self.framePerSec):
                self.updateFrame()
            actions = self.redisConn.getActions()
            self.doActions(actions)
            
            self.redisConn.setDynamicGameInfo(self.getDynamicGameInfo())
            self.redisConn.setStaticMapInfo(self.getStaticMapInfo())



class RedisConn:
    def setPlayerPos(self, pos):
        redisConn.set("playerPos", str(pos), ex=3600)

    def setDynamicGameInfo(self, info):
        print(info)
        redisConn.set("dynamicGameInfo", json.dumps(info), ex=3600)

    def setStaticMapInfo(self, info):
        redisConn.set("staticMapInfo", json.dumps(info), ex=3600)

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
