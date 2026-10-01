local isEditor = (Amaz.Macros and Amaz.Macros.EditorSDK) and true or false
local exports = exports or {}
local TextAnim = TextAnim or {}
TextAnim.__index = TextAnim
---@class TextAnim : ScriptComponent
---@field autoPlay boolean
---@field duration number
---@field curTime number
---@field progress number [UI(Range={0, 1}, Slider)]

local function clamp(x, a, b)
    return math.max(math.min(x, b), a)
end

-- must exist for registing module
function TextAnim:_registerModule(_module_path)
    local module = includeRelativePath(_module_path)
    if module and module.TEXT_STICKER then
        module = module.new(self)
    end
    return module
end

function TextAnim.getAEData()
    local aeTools = includeRelativePath("modules/AETools")
    local aeData = includeRelativePath("modules/AEData")
    local attrs = aeTools.new(aeData.ae_attribute)
    return attrs
end

function TextAnim.new()
    local self = setmetatable({}, TextAnim)

    local sticker = includeRelativePath("modules/TextSticker")
    setmetatable(TextAnim, sticker)
    setmetatable(self, TextAnim)

    -- vat Attr ----
    self.registerModules = { "LetterStyleMergeModule", "CaptionModule", "TextCloneModule", "RenderModule", "Sprite2DModule" }

    self.seq_material = nil

    return self
end


function TextAnim:textStart(comp) 

    self.c_module = self:getModule("CaptionModule")
    -- self.kw_module = self:getModule("KeyWordsStyle")
    -- self.attrs = self.getAEData()
    -- self.rootDir = getRootDir()
end
local function mix(a, b, x)
    return a * (1-x) + b * x
end

local function remap01(a,b,x)
    if x < a then return 0 end
    if x > b then return 1 end
    return (x-a)/(b-a)
end
function TextAnim:textInit()
    self.richText.canvas.renderToRT = false
    if isEditor then
    else
        self.renderer.material = self.material_template:instantiate()
    end
    self.material = self.renderer.material

    self.richText:forceTypeSetting()

    if self.c_module == nil or self.c_module:isLegal() == false then
        return
    end
    -- Amaz.LOGI("lrc has", "c_module")
    -- local t1 = {1,2,3,4,5}
    -- for k, v in ipairs(t1) do
    --     Amaz.LOGE("lrc "..tostring(k), tostring(v))
    -- end
    -- table.remove(t1)
    -- for k, v in ipairs(t1) do
    --     Amaz.LOGE("lrc "..tostring(k), tostring(v))
    -- end
    -- self.kw_module:setKeyWordsDefaultStyle(Amaz.Color(1,0,0,1))
    -- local canvasColor = self.richText.canvas.canvasColor 
    -- if canvasColor.x >= 0.99 and canvasColor.y >= 0.99 and canvasColor.z >= 0.99 then
    --     canvasColor:set(117/255, 52/255, 242/255, 1.0)
    -- end
    -- self.richText.canvas.canvasColor = canvasColor
    -- -- self.material:setVec4("u_canvasColor", canvasColor)
    -- self.richText.canvas.canvasEnabled = false
    -- self.c_module:init()

    -- self.c_module:splitPage(0, 1).LineCountLimit(3,2)
    -- self.c_module:splitPage(0, 1).wordCountPerPageLimit(1)
    -- self.c_module:splitPage(0, 1).LineCountLimit(1, 2)
    -- self.c_module:splitPage(0, 1).customWordLineCountLimit({{3,4,3},{3,2,2}}, true)
    -- self.c_module:splitPage(0, 1).customWordLineCountLimit({{1,2}}, true)
    self.c_module:splitPage(0, 1).Default()
    -- self.c_module:splitPage(0, 1).customWordLineCountLimit({{3,4},{1, 2, 1},{1,3}}, true)
    self.capDuration = self.c_module:getDuration()
    -- local width = Amaz.BuiltinObject:getOutputTextureWidth()
    -- local height = Amaz.BuiltinObject:getOutputTextureHeight()
    local initLetters = self.richText.letters:clone()
    self.oriLetterSpacing = self.richText.typeSettingParam.letterSpacing

    -- local isWrite = true

    -- for i = 1, self.richText.letters:size() do
    --     if self.richText.letters:get(i - 1).letterStyle.letterColorRGBA ~= Amaz.Color(1.0, 1.0, 1.0, self.richText.letters:get(i - 1).letterStyle.letterColorRGBA.a) then
    --         isWrite = false
    --     end
    -- end

    local function cubicOut(t)
        t = 1 - t
        return 1 - t * t * t
    end

    local function mix (x, y, a)
        return x + (y - x) * a
    end
    
    local readingPageFunc = function(_obj, _p, letters)
        -- Amaz.LOGI("lrc obj ".._p, tostring(_obj:getStr())..", "..tostring(_obj:getDuration()))
    end
    local beforeReadWordFunc = function(_obj, _p)
        local alpha = 0
        local oriLetters = _obj:getOriLetters()
        for i = 1, #_obj.letters do
            local oriInsColor = oriLetters[i].instanceColor
            _obj.letters[i].instanceColor = Amaz.Color(oriInsColor.r, oriInsColor.g, oriInsColor.b, 0)
            _obj.letters[i].letterStyle.letterAlpha = oriLetters[i].letterStyle.letterAlpha * alpha
            _obj.letters[i].position = _obj.letters[i].initialPosition
        end
    end
    local readingWordFunc = function(_obj, _p)

        local fontSize = 24
        if #_obj.letters >= 1 then
            fontSize =  _obj.letters[1].letterStyle.fontSize
        end
        local offsetX, offsetY
        if self.richText.typeSettingParam.typeSettingKind == Amaz.TypeSettingKind.HORIZONTAL then
            offsetX = 0
            offsetY = -fontSize * 4.0
        else
            offsetX = -fontSize * 4.0
            offsetY = 0
        end
        local tm = cubicOut(_p)
        local dx = mix(offsetX, 0, tm)
        local dy = mix(offsetY, 0, tm)

        -- Amaz.LOGE("lrc readingWordFunc", "dx="..dx..", dy="..dy)

        local alpha = _p
        local oriLetters = _obj:getOriLetters()
        -- local word = _obj:getCenter()
        for i = 1, #_obj.letters do
            _obj.letters[i].letterStyle.letterAlpha = oriLetters[i].letterStyle.letterAlpha * alpha
            local oriInsColor = oriLetters[i].instanceColor
            _obj.letters[i].instanceColor = Amaz.Color(oriInsColor.r, oriInsColor.g, oriInsColor.b, oriInsColor.a * alpha)
            local char = _obj.letters[i]
            local x = char.initialPosition.x + dx
            local y = char.initialPosition.y + dy
            char.position = Amaz.Vector2f(x, y)
        end
        
    end
    local afterReadWordFunc = function(_obj, _p)
        local alpha = 1
        local oriLetters = _obj:getOriLetters()
        for i = 1, #_obj.letters do
            local oriInsColor = oriLetters[i].instanceColor
            _obj.letters[i].instanceColor = oriInsColor
            _obj.letters[i].letterStyle.letterAlpha = oriLetters[i].letterStyle.letterAlpha * alpha
            _obj.letters[i].position = _obj.letters[i].initialPosition
        end
    end
   

    local pages = self.c_module:getPages()
    for i = 1, #pages do
        -- pages[i]:setReadingAnim(readingPageFunc)
        pages[i]:setWordBeforeReadAnim(beforeReadWordFunc)
        pages[i]:setWordReadingAnim(readingWordFunc)
        pages[i]:setWordAfterReadAnim(afterReadWordFunc)

        -- pages[i]:setLineBeforeReadAnim(beforeReadWordFunc)
        -- pages[i]:setLineReadingAnim(readingWordFunc)
        -- pages[i]:setLineAfterReadAnim(afterReadWordFunc)
    end
    
end

local function clamp(x, a, b)
    return math.min(math.max(x, a), b)
end

function TextAnim:textSeek(_time)

    local time = _time
    if isEditor then
        time = 4 * self.progress
        -- self.progress = clamp((time % self.capDuration) / self.capDuration, 0.0, 1.0)
    else
        self.progress = clamp(_time / math.min(self.capDuration, 0.2), 0.0, 1.0)
    end
    -- local page, word = self.c_module:animing(_time % self.capDuration)
    local page, word = self.c_module:animing(time)
    if page == nil then
        return 
    end
end

function TextAnim:textReset()
    self.richText.typeSettingParam.letterSpacing = self.oriLetterSpacing
end

exports.TextAnim = TextAnim
return exports
