

local KeyWordsStyle = {}
KeyWordsStyle.__index = KeyWordsStyle
KeyWordsStyle.TEXT_STICKER = "TEXT_STICKER"

function KeyWordsStyle.new(_sticker)
    local self = setmetatable({}, KeyWordsStyle)
    self.sticker = _sticker
    return self
end

local function layerCommonCompare (layer1, layer2)
    if (layer1.type ~= layer2.type) or (layer1.enable ~= layer2.enable) or (layer1.alpha ~= layer2.alpha) then
        return false
    end
    if layer1.renderType ~= layer2.renderType then
        return false
    end
    if layer1.renderType == 0 then
        if layer1.color ~= layer2.color then
            return false
        end
    elseif layer1.renderType == 1 then
        if (layer1.gradientAngle ~= layer2.gradientAngle) or (layer1.gradientMode ~= layer2.gradientMode) then
            return false
        end
        local gradientColors1 = layer1.gradientColors
        local gradientColors2 = layer2.gradientColors
        local gradientPoints1 = layer1.gradientPoints
        local gradientPoints2 = layer2.gradientPoints
        if gradientColors1:size() ~= gradientColors2:size() or gradientPoints1:size() ~= gradientPoints2:size() then
            return false
        end
        for i = 0, gradientColors1:size() - 1 do
            local color1 = gradientColors1:get(i)
            local color2 = gradientColors2:get(i)
            if color1 ~= color2 then
                return false
            end
        end

        for i = 0, gradientPoints1:size() - 1 do
            local point1 = gradientPoints1:get(i)
            local point2 = gradientPoints2:get(i)
            if point1 ~= point2 then
                return false
            end
        end
    elseif layer1.renderType == 2 then
        if layer1.texturePath ~= layer2.texturePath or
        layer1.textureFlipX ~= layer2.textureFlipX or
        layer1.textureFlipY ~= layer2.textureFlipY or
        layer1.textureScale ~= layer2.textureScale or
        layer1.textureAlpha ~= layer2.textureAlpha or
        layer1.textureAngle ~= layer2.textureAngle or
        layer1.textureRange ~= layer2.textureRange or
        layer1.textureBlend ~= layer2.textureBlend then
            return false
        end
    end

    if (layer1.strokeWidth ~= layer2.strokeWidth) then
        return false
    end
    if (layer1.shadowDistance ~= layer2.shadowDistance) or
    (layer1.shadowAngle ~= layer2.shadowAngle) or
    (layer1.shadowFeather ~= layer2.shadowFeather) then
        return false
    end
    return true
end

local function styleLayerCompare (layer1, layer2)
    if not layerCommonCompare(layer1, layer2) then
        return false
    end
    local shadowStroke1 = layer1.shadowStrokes
    local shadowStroke2 = layer2.shadowStrokes
    if shadowStroke1:size() ~= shadowStroke2:size() then
        return false
    end

    for i = 0, shadowStroke1:size() - 1 do
        if not layerCommonCompare(shadowStroke1:get(i), shadowStroke2:get(i)) then
            return false
        end
    end
    return true
end

local function compareLetterStyle (letter1, letter2)
    local letterStyle1 = letter1.letterStyle
    local letterStyle2 = letter2.letterStyle
    --- is flower text compare
    if letterStyle1:hasResLink() ~= letterStyle2:hasResLink() then
        return false
    end

    --- letter color compare
    if (letterStyle1.letterColorRGBA ~= letterStyle2.letterColorRGBA) or (letterStyle1.letterAlpha ~= letterStyle2.letterAlpha) then
        return false
    end

    --- letter default outline compare
    if (letterStyle1.outlineEnabled ~= letterStyle2.outlineEnabled) or
     (letterStyle1.outlineColorRGBA ~= letterStyle2.outlineColorRGBA) or 
     (letterStyle1.outlineAlpha ~= letterStyle2.outlineAlpha) or 
     (letterStyle1.outlineWidth ~= letterStyle2.outlineWidth) then
        return false
    end

    --- letter default shadow compare
    if (letterStyle1.shadowEnabled ~= letterStyle2.shadowEnabled) or
    (letterStyle1.shadowColorRGBA ~= letterStyle2.shadowColorRGBA) or
    (letterStyle1.shadowAlpha ~= letterStyle2.shadowAlpha) or
    (letterStyle1.shadowDistance ~= letterStyle2.shadowDistance) or
    (letterStyle1.shadowAngle ~= letterStyle2.shadowAngle) or 
    (letterStyle1.shadowSmooth ~= letterStyle2.shadowSmooth) then
        return false
    end

    --- font attribute compare
    if (letterStyle1.version ~= letterStyle2.version) or 
    (letterStyle1.fontId ~= letterStyle2.fontId) or
    (letterStyle1.fontfamily ~= letterStyle2.fontfamily) or
    (letterStyle1.fontSize ~= letterStyle2.fontSize) or
    (letterStyle1.fontStyle ~= letterStyle2.fontStyle) or
    (letterStyle1.italicAngle ~= letterStyle2.italicAngle) or
    (letterStyle1.boldValue ~= letterStyle2.boldValue) then
        return false
    end

    if letterStyle1:hasResLink() == false then
        return true
    end
    --- flower text fill attribute compare
    local fill1 = letterStyle1.fill
    local fill2 = letterStyle2.fill
    if not styleLayerCompare(fill1, fill2) then
        return false
    end

    --- flower text strokes attribute compare
    local strokes1 = letterStyle1.strokes
    local strokes2 = letterStyle2.strokes
    if strokes1:size() ~= strokes2:size() then
        return false
    end
    for i = 0, strokes1:size() - 1 do
        if not styleLayerCompare(strokes1:get(i), strokes2:get(i)) then
            return false
        end
    end

    --- flower text shadows attribute compare
    local shadows1 = letterStyle1.shadows
    local shadows2 = letterStyle2.shadows
    if shadows1:size() ~= shadows2:size() then
        return false
    end
    for i = 0, shadows1:size() - 1 do
        if not styleLayerCompare(shadows1:get(i), shadows2:get(i)) then
            return false
        end
    end

    --- flower text inner shadows attribute compare
    local innerShadows1 = letterStyle1.innerShadows
    local innerShadows2 = letterStyle2.innerShadows
    if innerShadows1:size() ~= innerShadows2:size() then
        return false
    end
    for i = 0, innerShadows1:size() - 1 do
        if not styleLayerCompare(innerShadows1:get(i), innerShadows2:get(i)) then
            return false
        end
    end

    return true
end

local function GetStringWordNum(str)
    local lenInByte = #str
    local count = 0
    local i = 1
    while true do
        local curByte = string.byte(str, i)
        if i > lenInByte then
            break
        end
        local byteCount = 1
        if curByte > 0 and curByte < 128 then
            byteCount = 1
        elseif curByte>=128 and curByte<224 then
            byteCount = 2
        elseif curByte>=224 and curByte<240 then
            byteCount = 3
        elseif curByte>=240 and curByte<=247 then
            byteCount = 4
        else
            break
        end
        -- local char = string.sub(str, i, i+byteCount-1)
        i = i + byteCount
        count = count + 1
    end
    return count
end

function KeyWordsStyle:setKeyWordsDefaultStyle (color)
    if self.sticker.rawCaptionStr == nil then
        return
    end
    local captionInfo = cjson.decode(self.sticker.rawCaptionStr)
    local keyLettersList = Amaz.Vector()
    local nonKeyLettersList = Amaz.Vector()
    local oriLetters = self.sticker.richText.letters
    local startIdx = 0
    local endIdx = 0
    for key, value in pairs(captionInfo.words) do
        local word = value
        local isKeyWord = word.is_key

        local wordLen = GetStringWordNum(word.text)

        endIdx = startIdx + wordLen - 1

        for i = startIdx, endIdx do
            local letter = oriLetters:get(i)
            if letter.utf8 ~= " " and letter.utf8 ~= "\n" then
                if isKeyWord == true then
                    keyLettersList:pushBack(letter)
                else
                    nonKeyLettersList:pushBack(letter)
                end
            end
        end
        startIdx = endIdx + 1
    end

    local hasDefaultSet = false
    for i = 0, keyLettersList:size() - 1 do
        local keyLetter = keyLettersList:get(i)
        local differentNum = 0
        for j = 0, nonKeyLettersList:size() - 1 do
            local normalLetter = nonKeyLettersList:get(j)
            differentNum = compareLetterStyle(keyLetter, normalLetter) and differentNum - 1 or differentNum + 1
        end
        if differentNum >= 0 then
            hasDefaultSet = true
            break
        end
    end
    if hasDefaultSet == false then
        for i = 0, keyLettersList:size() - 1 do
            local keyLetter = keyLettersList:get(i)
            keyLetter.letterStyle.letterColorRGBA = color:copy()
        end
    end
    return hasDefaultSet
end

function KeyWordsStyle:init()
    Amaz.LOGE("lrc module init", tostring("KeyWordsStyle"))
    self:setKeyWordsStyle()
end

function KeyWordsStyle:setKeyWordsStyle()
    if self.sticker.rawCaptionKeywordStylesStr == nil then
        return
    end
    local keywordStyles = cjson.decode(self.sticker.rawCaptionKeywordStylesStr)
    -- TODO: like setKeyWordsDefaultStyle
end

return KeyWordsStyle