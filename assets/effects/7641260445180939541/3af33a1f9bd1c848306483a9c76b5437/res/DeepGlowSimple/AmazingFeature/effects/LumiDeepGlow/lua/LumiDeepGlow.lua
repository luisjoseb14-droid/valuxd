local isEditor = (Amaz.Macros and Amaz.Macros.EditorSDK) and true or false
local exports = exports or {}
local LumiDeepGlow = LumiDeepGlow or {}
LumiDeepGlow.__index = LumiDeepGlow
---@class LumiDeepGlow : ScriptComponent
---@field radius number [UI(Range={0, 2000}, Drag)]
---@field exposure number [UI(Range={0.0, 5.0}, Drag)]
---@field ratio number [UI(Range={0, 2}, Drag)]
---@field rotate number 
---@field blendMode string [UI(Option={"Add","Screen"})]
---@field ca bool 
---@field redOffset number [UI(Range={-.1, 0.1}, Drag)]
---@field greenOffset number [UI(Range={-0.1, 0.1}, Drag)]
---@field blueOffset number [UI(Range={-0.1, 0.1}, Drag)]
---@field glowFromAlpha number [UI(Range={0.0, 1.0}, Drag)]
---@field tint bool
---@field tintColor Color [UI(NoAlpha)] 
---@field tintMode string [UI(Option={"Normal","Multiply","Overlay", "Softlight"})]
---@field tintMix number [UI(Range={0.0, 1.0}, Drag)]
---@field sourceOpacity number [UI(Range={0., 1.}, Drag)]
---@field gammaCorrect Bool
---@field gammaValue number [UI(Range={1., 4.}, Drag)]
---@field glowIter int [UI(Range={1, 8}, Slider)]
---@field stepsMult number [UI(Range={0.1, 10.0}, Drag)]
---@field downSample number [UI(Range={0.5, 1.0}, Drag)]
---@field quality number [UI(Range={0.5, 1.0}, Drag)]
---@field InputTex Texture
---@field OutputTex Texture
---@field lumiSharedRt Vector [UI(Type="Texture")]

local AE_EFFECT_TAG = 'AE_EFFECT_TAG LumiTag'

local function createRenderTexture(width, height, filterMag, filterMin)
    local rt = Amaz.RenderTexture()
    rt.width = width
    rt.height = height
    rt.depth = 1
    rt.filterMag = filterMag or Amaz.FilterMode.LINEAR
    rt.filterMin = filterMin or Amaz.FilterMode.LINEAR
    rt.filterMipmap = Amaz.FilterMipmapMode.NONE
    rt.attachment = Amaz.RenderTextureAttachment.NONE
    return rt
end

local function setRenderTexSize(rt, width, height)
    if rt == nil or width <= 0 or height <= 0 then
        return
    end
    if rt.width ~= width or rt.height ~= height then
        rt.width = width
        rt.height = height
    end
end

local clamp = function(value, min, max)
    return math.max(math.min(value, max), min)
end

local function goldenRatio(n)
    local sequence = {1, 1}
    for i = 2, n - 1 do sequence[i + 1] = sequence[i] + sequence[i - 1] end
    return sequence
end

local function inverseSqrFalloff(distance, radius)
    local maxDistance = radius
    local falloffFactor = 0.05
    local attenuation = math.pow(falloffFactor, distance / maxDistance)
    return attenuation
end

local function mapRadiusToStepsMult(radius)
    local minRadius = 500
    local maxRadius = 2000
    local minStepsMult = 1.0
    local maxStepsMult = 2.5

    if radius < minRadius then
        return minStepsMult
    end

    local t = (radius - minRadius) / (maxRadius - minRadius)
    local stepsMult = minStepsMult + (maxStepsMult - minStepsMult) * t

    return stepsMult
end

local tintModes = {
    ["Normal"] = 0, 
    ["Multiply"] = 1, 
    ["Overlay"] = 2, 
    ["Softlight"] = 3
}

function LumiDeepGlow.new(construct, ...)
    local self = setmetatable({}, LumiDeepGlow)

    self.__lumi_type = "lumi_effect"
    self.__lumi_rt_pingpong_type = "custom"

    self.radius = 1.
    self.exposure = 1.
    self.rotate = 0.
    self.ratio = 1.

    self.blendMode = "Screen"
    self.sourceOpacity = 0.

    self.ca = false
    self.redOffset = 0.01
    self.greenOffset = -0.01
    self.blueOffset = 0.
    self.glowFromAlpha = 1.

    self.tint = true
    self.tintColor = Amaz.Color(1., 0., 0.)
    self.tintMode = "Multiply"
    self.tintMix = 1.

    self.gammaCorrect = true
    self.gammaValue = 2.2

    self.glowIter = 8
    self.stepsMult = 1.
    self.downSample = 1.
    self.quality = 1.

    self.InputTex = nil
    self.preProcessTex = nil
    self.blurTex = nil
    self.blurTex1 = nil
    self.bufferA = nil
    self.bufferB = nil
    self.OutputTex = nil

    self.numLayers = 8

    return self
end

function LumiDeepGlow:setEffectAttr(key, value, comp)
    local function _setEffectAttr(_key, _value)
        if self[_key] ~= nil then
            self[_key] = _value
            if comp and comp.properties ~= nil then
                comp.properties:set(_key, _value)
            end
        end
    end

    if key == "tintMode" then
        local tintMode = "Normal"
        if value == 0 then
            tintMode = "Normal"
        elseif value == 1 then
            tintMode = "Multiply"
        elseif value == 2 then
            tintMode = "Overlay"
        elseif value == 3 then
            tintMode = "Softlight"
        end
        _setEffectAttr(key, tintMode)
    elseif key == "blendMode" then
        local blendMode = "Add"
        if value == 1 then blendMode = "Screen" end
        _setEffectAttr(key, blendMode)
    elseif key == "tintColor" then
        local color = Amaz.Color(value:get(0), value:get(1), value:get(2), 1)
        _setEffectAttr(key, color)
    else
        _setEffectAttr(key, value)
    end
end

function LumiDeepGlow:constructGlowIters(entity)
    local glowIter = {}
    glowIter.entity = entity
    glowIter.downScale = 0.5
    glowIter.radius = 0.5
    glowIter.stride = 1.
    glowIter.sigma = 1.
    glowIter.stepsMult = 1
    glowIter.downSample = 1
    glowIter.maxSteps = 16
    glowIter.angle = 0
    glowIter.ratio = 1.
    glowIter.rotate = 1.
    glowIter.gammaCorrect = true
    glowIter.gammaValue = 2.2
    glowIter.comp = false
    glowIter.opacity = 1.0
    glowIter.mult = 1.0

    glowIter.InputTex = nil
    glowIter.bufferA = nil
    glowIter.bufferB = nil
    glowIter.OutputTex = nil

    glowIter.camDown = entity:searchEntity("CameraDown"):getComponent("Camera")
    glowIter.matDown = entity:searchEntity("PassDown"):getComponent("MeshRenderer").material
    glowIter.camBlurX = entity:searchEntity("CameraBlurX"):getComponent("Camera")
    glowIter.matBlurX = entity:searchEntity("PassBlurX"):getComponent("MeshRenderer").material
    glowIter.matBlurY = entity:searchEntity("PassBlurY"):getComponent("MeshRenderer").material
    glowIter.camBlurY = entity:searchEntity("CameraBlurY"):getComponent("Camera")
    glowIter.matComp = entity:searchEntity("PassComp"):getComponent("MeshRenderer").material
    glowIter.camComp = entity:searchEntity("CameraComp"):getComponent("Camera")

    return glowIter
end

function LumiDeepGlow:updateGlowIters()
    for i = 1, self.numLayers do
        local glowIter = self.GlowIter[i]

        if glowIter.entity.visible then

            local width = glowIter.OutputTex.width
            local height = glowIter.OutputTex.height
            local downScaleW = width * glowIter.downScale
            local downScaleH = height * glowIter.downScale
        
            -- Set RT sizes
            setRenderTexSize(glowIter.bufferA, downScaleW, downScaleH)
            setRenderTexSize(glowIter.bufferB, downScaleW, downScaleH)
        
            -- Set Tex
            if glowIter.bufferA then
                glowIter.camDown.renderTexture = self.bufferA
                glowIter.camBlurY.renderTexture = self.bufferA
            end
            if glowIter.bufferB then glowIter.camBlurX.renderTexture = glowIter.bufferB end
            if glowIter.OutputTex then glowIter.camComp.renderTexture = glowIter.OutputTex end
        
            glowIter.matDown:setTex("u_inputTex", glowIter.InputTex)
            glowIter.matBlurX:setTex("u_inputTex", glowIter.bufferA)
            glowIter.matBlurY:setTex("u_inputTex", glowIter.bufferB)
        
            -- Set Parms
            local ratio = clamp(glowIter.ratio, 0, 2)
            local rotate = glowIter.rotate
            local stepsInt = 1. / glowIter.downSample
            local stride = glowIter.stride / glowIter.stepsMult
            local aspect = Amaz.Vector2f(width, height) / math.max(width, height)
            local stepsX = math.min(glowIter.steps, glowIter.maxSteps) * ratio
            local stepsY = math.min(glowIter.steps, glowIter.maxSteps) * (2.0 - ratio)
        
            if glowIter.gammaCorrect then
                glowIter.matBlurX:setFloat("u_gammaValue", glowIter.gammaValue)
                glowIter.matBlurY:setFloat("u_gammaValue", glowIter.gammaValue)
                glowIter.matComp:setFloat("u_gammaValue", glowIter.gammaValue)
            else
                glowIter.matBlurX:setFloat("u_gammaValue", 1)
                glowIter.matBlurY:setFloat("u_gammaValue", 1)
                glowIter.matComp:setFloat("u_gammaValue", 1)
            end
        
            glowIter.matBlurX:setFloat("u_steps", stepsX)
            glowIter.matBlurX:setFloat("u_stepsInt", stepsInt) -- for controlling i 
            glowIter.matBlurX:setFloat("u_stride", stride)
            glowIter.matBlurX:setFloat("u_sigma", glowIter.sigma)
            glowIter.matBlurX:setFloat("u_angle", glowIter.angle)
            glowIter.matBlurX:setFloat("u_rotate", rotate)
            glowIter.matBlurX:setVec2("u_aspect", aspect)
        
            glowIter.matBlurY:setFloat("u_steps", stepsY)
            glowIter.matBlurY:setFloat("u_stepsInt", stepsInt) -- for controlling i 
            glowIter.matBlurY:setFloat("u_stride", stride)
            glowIter.matBlurY:setFloat("u_sigma", glowIter.sigma)
            glowIter.matBlurY:setFloat("u_angle", glowIter.angle + 90)
            glowIter.matBlurY:setFloat("u_rotate", rotate)
            glowIter.matBlurY:setVec2("u_aspect", aspect)
        
            glowIter.matComp:setTex("u_inputTex", glowIter.InputTex)
            glowIter.matComp:setTex("u_blurTex", glowIter.bufferA)
            glowIter.matComp:setFloat("u_opacity", glowIter.opacity)
            glowIter.matComp:setFloat("u_mult", glowIter.mult)
            glowIter.matComp:setInt("u_comp", glowIter.comp and 1 or 0)
            glowIter.matComp:setInt("u_blendMode", glowIter.blendMode)

        end
    end
end

function LumiDeepGlow:onStart(comp)
    self.entity = comp.entity
    self.TAG = AE_EFFECT_TAG .. ' ' .. self.entity.name

    self.matPreprocess = comp.entity:searchEntity("PassPreprocess"):getComponent("MeshRenderer").material
    self.camPreprocess = comp.entity:searchEntity("CameraPreprocess"):getComponent("Camera")

    self.GlowIter = {}
    for i = 1, self.numLayers do
        local name = "GlowIter_" .. i
        self.GlowIter[i] = self:constructGlowIters(comp.entity:searchEntity(name))
    end

    self.matPostprocess = comp.entity:searchEntity("PassPostprocess"):getComponent("MeshRenderer").material
    self.camPostprocess = comp.entity:searchEntity("CameraPostprocess"):getComponent("Camera")

    if self.lumiSharedRt and self.lumiSharedRt:size() > 0 then
        self.blurTex = self.lumiSharedRt:get(0)
        self.blurTex1 = self.lumiSharedRt:get(1)
    end

    local width = self.OutputTex.width
    local height = self.OutputTex.height

    self.preProcessTex = createRenderTexture(width, height)
    self.bufferA = createRenderTexture(width, height)
    self.bufferB = createRenderTexture(width, height)
end

function LumiDeepGlow:onUpdate(comp, deltaTime)
    if self.preProcessTex then
        self.camPreprocess.renderTexture = self.preProcessTex
    end
    if self.OutputTex then self.camPostprocess.renderTexture = self.OutputTex end

    local width = self.OutputTex.width
    local height = self.OutputTex.height

    setRenderTexSize(self.preProcessTex, width, height)
    setRenderTexSize(self.blurTex, width, height)
    setRenderTexSize(self.blurTex1, width, height)

    --- Preprocess
    self.matPreprocess:setTex("u_inputTex", self.InputTex)
    self.matPreprocess:setInt("u_gamma", self.gammaCorrect and 1 or 0)
    self.matPreprocess:setFloat("u_gammaValue", self.gammaValue)
    self.matPreprocess:setInt("u_ca", self.ca and 1 or 0)
    self.matPreprocess:setFloat("u_redOffset", self.redOffset * 0.05)
    self.matPreprocess:setFloat("u_greenOffset", self.greenOffset * 0.05)
    self.matPreprocess:setFloat("u_blueOffset", self.blueOffset * 0.05)
    self.matPreprocess:setFloat("u_glowFromAlpha", self.glowFromAlpha)

    -- Glow Iter Parameters
    local radius = self.radius * 5
    local radiusFactor = radius / 500
    local quality = self.quality
    local exposure = self.exposure
    local stepsMult = self.stepsMult * mapRadiusToStepsMult(radius)
    local glowIterCount = math.floor(self.glowIter)

    local downScale = {}
    downScale[1] = 0.5 * quality
    downScale[self.glowIter] = 0.5 * quality
    for i = 2, self.glowIter - 1 do downScale[i] = 0.25 * quality end

    local stride = {}
    local maxSteps = {}
    local steps = {}
    local goldenRatioSequence = goldenRatio(self.numLayers)
    local basePercentage = 0.001
    for i = 1, self.numLayers do
        maxSteps[i] = math.min(i * radiusFactor, i * 6)
        stride[i] = radiusFactor * i * basePercentage
        steps[i] = radiusFactor * goldenRatioSequence[i]
    end

    local inputTex = {}
    local outputTex = {}
    for i = 1, self.numLayers do
        table.insert(inputTex, i % 2 == 0 and self.blurTex or self.blurTex1)
        table.insert(outputTex, i % 2 == 1 and self.blurTex or self.blurTex1)
    end
    inputTex[1] = self.preProcessTex

    for i = 1, self.numLayers do
        local glowIter = self.GlowIter[i]
        if i > glowIterCount then
            glowIter.entity.visible = false
        else
            glowIter.entity.visible = true
            glowIter.InputTex = inputTex[i]
            glowIter.OutputTex = outputTex[i]
            glowIter.bufferA = self.bufferA
            glowIter.bufferB = self.bufferB

            glowIter.downScale = downScale[i]
            glowIter.steps = steps[i]
            glowIter.stride = stride[i]
            glowIter.maxSteps = maxSteps[i]
            glowIter.sigma = 4.

            glowIter.stepsMult = stepsMult
            glowIter.downSample = self.downSample
            glowIter.ratio = self.ratio
            glowIter.rotate = self.rotate

            local distance = i / self.numLayers
            local falloff = inverseSqrFalloff(distance, i)

            glowIter.opacity = self.gammaValue / i * falloff
            glowIter.mult = exposure
            glowIter.gammaValue = self.gammaValue
            glowIter.comp = true
            glowIter.blendMode = self.blendMode == "Screen" and 0 or 1
        end
    end

    self:updateGlowIters()
    self.matPostprocess:setInt("u_tintMode", tintModes[self.tintMode] or 0)

    -- Post Process
    if (glowIterCount % 2 == 0) then
        self.matPostprocess:setTex("u_blurTex", self.blurTex1)
    else
        self.matPostprocess:setTex("u_blurTex", self.blurTex)
    end

    self.matPostprocess:setTex("u_inputTex", self.InputTex)
    self.matPostprocess:setTex("u_thresholdTex", self.preProcessTex)
    self.matPostprocess:setTex("u_blurTex", self.blurTex)
    self.matPostprocess:setInt("u_gammaCorrect", self.gammaCorrect and 1 or 0)
    self.matPostprocess:setFloat("u_gammaValue", self.gammaValue)
    self.matPostprocess:setInt("u_tint", self.tint and 1 or 0)
    self.matPostprocess:setVec3("u_tintColor", Amaz.Vector3f(self.tintColor.r, self.tintColor.g, self.tintColor.b))
    self.matPostprocess:setFloat("u_tintMix", self.tintMix)
    self.matPostprocess:setFloat("u_srcOpacity", self.sourceOpacity)
end

exports.LumiDeepGlow = LumiDeepGlow
return exports
