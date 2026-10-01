local exports = exports or {}
local Projection = Projection or {}
Projection.__index = Projection
---@class Projection : ScriptComponent
---@field curTime number
---@field scale number
---@field backAlpha number [UI(Range={0, 1}, Slider)]
---@field shakeTime number [UI(Range={0, 1}, Slider)]
---@field shakeScale number [UI(Range={0, 2}, Slider)]
---@field mixWithBlack number [UI(Range={0, 1}, Slider)]
---@field offsetY_0 number [UI(Range={-1, 1}, Slider)]
---@field InputTex Texture
---@field OutputTex Texture

function Projection.new(construct, ...)
    local self = setmetatable({}, Projection)
    if construct and Projection.constructor then Projection.constructor(self, ...) end

    self.InputTex = nil
    self.OutputTex = nil

    self.startTime = 0.0
    self.endTime = 3.0
    self.curTime = 0.0
    self.shakeTime = 0.0
    -- effect adjust params
    self.scale = 1.0
    self.shakeScale = 1.0
    self.backAlpha = 1
    self.mixWithBlack = 0.0
    self.textExpandRatio = Amaz.Vector2f(1, 1)
    self.offsetY_0 = 0.0
    return self
end

local function mix(a, b, x)
    return a * (1 - x) + b * x
end
local function CreateShakeFunction(duration, shakeKeyframes)
    local shakeState = {
        duration = duration or 1.0,
        lastTime = 0.0,
        x1 = 0,
        y1 = 0,
        x2 = 0,
        y2 = 0,
        updateFlag = false
    }

    if not shakeKeyframes then
        shakeKeyframes = {
            { frame = 0,   value = 0.0 },
            { frame = 50,  value = 0.04 },
            { frame = 87,  value = 0.02 },
            { frame = 125, value = 0.04 },
            { frame = 150, value = 0.04 }
        }
    end

    local totalFrames = shakeKeyframes[#shakeKeyframes].frame

    return function(time, scale, w, h)
        scale = scale or 1.0
        w = w or Amaz.BuiltinObject:getInputTextureWidth()
        h = h or Amaz.BuiltinObject:getInputTextureHeight()

        local progress = (time / shakeState.duration) % 1.0
        local currentFrame = progress * totalFrames

        local shakeValue = 0.0
        for i = 2, #shakeKeyframes do
            if currentFrame <= shakeKeyframes[i].frame then
                local prevFrame = shakeKeyframes[i - 1].frame
                local nextFrame = shakeKeyframes[i].frame
                local t = (currentFrame - prevFrame) / (nextFrame - prevFrame)
                shakeValue = mix(shakeKeyframes[i - 1].value, shakeKeyframes[i].value, t)
                break
            end
        end

        local x = math.floor(shakeState.lastTime * 9.2)
        local y = math.floor(time * 9.2)
        local f = (time * 9.2) % 1.0

        shakeState.updateFlag = (x ~= y)

        if shakeState.updateFlag then
            shakeState.x1 = shakeState.x2
            shakeState.y1 = shakeState.y2
            shakeState.x2 = (math.random() * 2 - 1) * 0.4 + 0.2
            shakeState.y2 = (math.random() * 2 - 1) * 0.4 + 0.2
        end

        local tx = mix(shakeState.x1, shakeState.x2, f) * shakeValue * 0.45 * w / h
        local ty = mix(shakeState.y1, shakeState.y2, f) * shakeValue * 0.45

        shakeState.lastTime = time

        return tx, ty
    end
end
function Projection:constructor()

end

function Projection:onStart(comp)
    self.first = true
    self.pass0Material = comp.entity:searchEntity("pass"):getComponent("MeshRenderer").material
    self.pass0Camera = comp.entity:searchEntity("cam"):getComponent("Camera")
    self.updateShake = CreateShakeFunction(1.0)
end

function Projection:setEffectAttr(key, value, comp)
    local function _setEffectAttr(_key, _value, _force)
        if _force or self[_key] ~= nil then
            self[_key] = _value
            if comp and comp.properties ~= nil then
                comp.properties:set(_key, _value)
            end
        end
    end

    _setEffectAttr(key, value)
end

function Projection:onUpdate(comp, detalTime)
    if self.first == nil then
        self:onStart(comp)
    end


    self:seekToTime(comp, self.curTime - self.startTime)
end

function Projection:seekToTime(comp, time)
    local w = Amaz.BuiltinObject:getInputTextureWidth()
    local h = Amaz.BuiltinObject:getInputTextureHeight()
    self.pass0Camera.renderTexture = self.OutputTex
    self.pass0Material:setTex("mainTex", self.InputTex)
    self.pass0Material:setFloat("scale", 1 / self.scale)
    self.pass0Material:setFloat("back_alpha", self.backAlpha)
    self.pass0Material:setFloat("mix_with_black", self.mixWithBlack)
    self.pass0Material:setVec2("textExpandRatio",
        Amaz.Vector2f(self.textExpandRatio.x + 0.000001, self.textExpandRatio.y + 0.000001))
    self.pass0Material:setFloat("offsetY_0", self.offsetY_0)

  
    local tx, ty = self.updateShake(self.shakeTime*10., 1.0, w, h)
    self.pass0Material:setFloat("shakeX", tx)
    self.pass0Material:setFloat("shakeY", ty)
    self.pass0Material:setFloat("shakeScale", self.shakeScale)
end

exports.Projection = Projection
return exports
