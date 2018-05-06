import os
import sys

import redis
import random
import json

if os.environ.get("REDIS_URL"):
    REDIS_URL = os.environ.get("REDIS_URL")
else:
    REDIS_URL = None
    print("No redis url!")
    sys.exit(1)
    
pool = redis.BlockingConnectionPool.from_url(REDIS_URL, max_connections=9)
redisConn = redis.Redis(connection_pool = pool)
class Point:
    def __init__(self, x = 0; y = 0):
        self.x = x
        self.y = y
    def getDist(self, p):
        return ((p.x - self.x)**2 + (p.y-self.y)**2)**0.5
    def getAngle(self, p):
        return math.atan2(p.y-self.y, p.x-self.x)
    def getShift(self, angle, length):
        x = length*math.sin(angle) + self.x
        y = length*math.cos(angle) + self.y
        return Point(x, y)

class MapCell:
    def __init__(self):
        self.walkable = True

class Map:
    def __init__(self, height = 30, width = 30):
        self.height = height
        self.width = width
        self.data = [[MapCell() for i in self.width] for j in range(self.height)]
        self.pixelSize = 32

    def collide(self, obj):
        if obj.pos.x - obj.width/2 < 0 or obj.pos.x + obj.width/2 > self.pixelSize * self.width \
                or obj.pos.y - obj.height/2 < 0 or obj.pos.y + obj.height/2 > self.pixelSize * self.height:
                    return True
        for i in range(int((obj.pos.x - obj.width/2)/self.pixelSize), int((obj.pos.x + obj.width/2)/self.pixelSize)+1):
            for j in range(int((obj.pos.y - obj.height/2)/self.pixelSize), int((obj.pos.y + obj.height/2)/self.pixelSize)+1):
                if self.data[j][i].walkable == False:
                    return True
        return False


class GameObject:
    def __init__(self):
        self.pos = Point()
        self.moveDestination = Point()
        self.moveAngle = 0
        self.speed = 0
        self.width = 32
        self.height = 32
    def updateAngle(self):
        self.moveAngle = self.pos.getAngle(self.moveDestination)
    def move(self, time, m):
        if time != 0:
            newPos = self.pos.getShift(self.moveAngle, self.speed*time)
            if not m.collide(newPos)
                self.pos = newPos

class Player(GameObject):
    def __init__(self):
        GameObject.__init__(self)
        self.speed = 1

class Game:
    def __init__(self):
        self.width = 30
        self.height = 30
        self.pixelSize = 32
        self.redisConn = RedisConn()
        self.framePerSec = 10
        self.players = []

    def updatePlayers(self):
        for player in self.players:
            players.move(1.0/self.framePerSec)


    def updateFrame(self):

    def run(self):
        p = Player()
        while True:
            p.x = p.x + random.uniform(0,1)
            p.y = p.y + random.uniform(0,1)
            if p.x > self.width:
                p.x -= self.width
            if p.y > self.height:
                p.y -= self.height
            self.redisConn.setPlayerPos(json.dumps({'x':p.x, 'y':p.y}))


class RedisConn:
    def setPlayerPos(self, pos):
        redisConn.set("playerPos", str(pos), ex=3600)

if __name__ == '__main__':
    g = Game()
    g.run()
