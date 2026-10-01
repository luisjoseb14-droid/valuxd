--[[
    Script Name: LetterStyleMergeModule.lua
    Version: 1.4
    Update Data: 2024.10.29
--]]

--[[  ****************************************
    Common Func
--    **************************************** ]]
local Common = {
    isEditor = (Amaz.Macros and Amaz.Macros.EditorSDK) and true or false,

    readStrFromFile = function(file_path)
        local file = io.input(file_path)
        local text = io.read("*a")
        return text
    end,

    isLegalStr = function(_str)
        local ilegal = _str == " " or _str == "\n"
        return not ilegal
    end,

    getLetterCount = function(_str)
        local str = _str
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
            elseif curByte >= 128 and curByte < 224 then
                byteCount = 2
            elseif curByte >= 224 and curByte < 240 then
                byteCount = 3
            elseif curByte >= 240 and curByte <= 247 then
                byteCount = 4
            else
                break
            end
            -- local char = string.sub(str, i, i+byteCount-1)
            i = i + byteCount
            count = count + 1
        end
        return count
    end,

    fakeMergeData = {
        -- letterColorRGBA = Amaz.Color(0.5, 1, 0.5, 1),
        -- fontSize = 30
    },

}
--[[  ****************************************
    LetterStyleMergeModule: manager all the CloneText
--    **************************************** ]]
local LetterStyleMergeModule = {}
LetterStyleMergeModule.__index = LetterStyleMergeModule
LetterStyleMergeModule.TEXT_STICKER = "TEXT_STICKER"


function LetterStyleMergeModule.new(_sticker)
    local self = setmetatable({}, LetterStyleMergeModule)

    self.sticker = _sticker
    self.relative = false
    return self
end

function LetterStyleMergeModule:setRelative(relative)
    self.relative = relative
end

function LetterStyleMergeModule:merge(_baseLetter, _mergeLetter, _keywordIdx, _blendMode)
    -- Amaz.LOGE("lrc merge base "..tostring(_baseLetter.utf8), tostring(_baseLetter.letterStyle.letterColorRGBA))
    -- Amaz.LOGE("lrc merge merged "..tostring(_mergeLetter.utf8), tostring(_mergeLetter.letterStyle.letterColorRGBA))
    if Common.isEditor then
        self:fakeMerge(_baseLetter, _mergeLetter)
    else
        self:realMerge(_baseLetter, _mergeLetter, _keywordIdx, _blendMode)
    end
end

function LetterStyleMergeModule:realMerge(_baseLetter, _mergeLetter, _keywordIdx, _blendMode)
    local keywordStyle = self:getKeywordStyle()
    if keywordStyle == nil then
        _baseLetter.letterStyle.letterColorRGBA = _mergeLetter.letterStyle.letterColorRGBA
        return
    end

    if keywordStyle == nil or not (#keywordStyle > 0) then
        return
    end

    local count = #keywordStyle
    local styleIndex = (_keywordIdx - 1) % count + 1

    if keywordStyle[styleIndex].styles == nil or not (#keywordStyle[styleIndex].styles > 0) then
        return
    end

    local style = keywordStyle[styleIndex].styles[1]

    if style == nil then
        return
    end

    local fontSize = _baseLetter.letterStyle.fontSize
    local function setNonEffectStyle()
        if _blendMode == "ignoreKeywordFontsize" then
            _baseLetter.letterStyle.fontSize = fontSize
        else
            if not self.relative then
                _baseLetter.letterStyle.fontSize = _mergeLetter.letterStyle.fontSize
            end
        end

        -- set font's about
        if style.font then
            _baseLetter.letterStyle.fontId = _mergeLetter.letterStyle.fontId
            _baseLetter.letterStyle.fontfamily = _mergeLetter.letterStyle.fontfamily
        end

        -- set fontStyle's about
        if style.bold == true or style.italic == true then
            _baseLetter.letterStyle.fontStyle = _mergeLetter.letterStyle.fontStyle
        end

        if style.underline then
            _baseLetter.letterStyle.fontDecoration = _mergeLetter.letterStyle.fontDecoration
        end

        -- fill's content
        if style.fill then
            _baseLetter.letterStyle.letterColorRGBA = _mergeLetter.letterStyle.letterColorRGBA
            _baseLetter.letterStyle.fill = _mergeLetter.letterStyle.fill:clone()
        end

        -- stroke's content
        if style.strokes and #style.strokes > 0 then
            _baseLetter.letterStyle.strokes = _mergeLetter.letterStyle.strokes:clone()
        end

        -- shadows's content
        if style.shadows and #style.shadows > 0 then
            _baseLetter.letterStyle.shadows = _mergeLetter.letterStyle.shadows:clone()
        end

        -- inner_shadows's content, ONLY flower word has
        if style.inner_shadows and #style.inner_shadows > 0 then
            _baseLetter.letterStyle.innerShadows = _mergeLetter.letterStyle.innerShadows:clone()
        end

        -- bloom's content
        if style.bloom and _baseLetter.letterStyle.bloomEnabled ~= nil then
            _baseLetter.letterStyle.bloomEnabled = _mergeLetter.letterStyle.bloomEnabled
            _baseLetter.letterStyle.bloomId = _mergeLetter.letterStyle.bloomId
            _baseLetter.letterStyle.bloomPath = _mergeLetter.letterStyle.bloomPath
            _baseLetter.letterStyle.bloomColorCustomized = _mergeLetter.letterStyle.bloomColorCustomized
            _baseLetter.letterStyle.bloomColor = _mergeLetter.letterStyle.bloomColor
            _baseLetter.letterStyle.bloomStrength = _mergeLetter.letterStyle.bloomStrength
            _baseLetter.letterStyle.bloomRange = _mergeLetter.letterStyle.bloomRange
            _baseLetter.letterStyle.bloomDirX = _mergeLetter.letterStyle.bloomDirX
            _baseLetter.letterStyle.bloomDirY = _mergeLetter.letterStyle.bloomDirY
            _baseLetter.letterStyle.bloomBlurDegree = _mergeLetter.letterStyle.bloomBlurDegree
        end

        -- background's content
        if style.background and _baseLetter.letterStyle.keywordsbackground ~= nil then
            _baseLetter.letterStyle.keywordsbackground = _mergeLetter.letterStyle.keywordsbackground
        end
    end

    _baseLetter.utf8 = _mergeLetter.utf8
    if style.effectStyle then
        _baseLetter.letterStyle = _mergeLetter.letterStyle:clone()
        if _blendMode == "ignoreKeywordFontsize" then
            _baseLetter.letterStyle.fontSize = fontSize
        end
        return
        -- _baseLetter.letterStyle.effectStyleId = _mergeLetter.letterStyle.effectStyleId
        -- _baseLetter.letterStyle.effectStylePath = _mergeLetter.letterStyle.effectStylePath
    else
        if _baseLetter.letterStyle.effectStylePath ~= _mergeLetter.letterStyle.effectStylePath then
            _baseLetter.letterStyle = _mergeLetter.letterStyle:clone()
            if _blendMode == "ignoreKeywordFontsize" then
                _baseLetter.letterStyle.fontSize = fontSize
            end
            return
        end
    end

    setNonEffectStyle()

end

function LetterStyleMergeModule:init()
    if Common.isEditor then
        local rootDir = self.sticker.entity.scene.assetMgr.rootDir
        self.rawKeywordStyleStr = Common.readStrFromFile(rootDir .. "test/fake_kw_style1.json")
    end

    self.keywordStyle = nil
end

function LetterStyleMergeModule:seek()

end

function LetterStyleMergeModule:fakeMerge(baseLetter, mergedLetter)
    if Common.fakeMergeData.letterColorRGBA then
        baseLetter.letterStyle.letterColorRGBA = Common.fakeMergeData.letterColorRGBA
    end
    if Common.fakeMergeData.fontSize then
        baseLetter.letterStyle.fontSize = Common.fakeMergeData.fontSize
    end
end

function LetterStyleMergeModule:getKeywordStyle()
    if self.rawKeywordStyleStr and self.keywordStyle == nil then
        self.keywordStyle = {}
        local contents = cjson.decode(self.rawKeywordStyleStr)
        if type(contents) == "table" then
            if #contents > 0 then
                for _, style in ipairs(contents) do
                    table.insert(self.keywordStyle, style)
                end
            else
                self.keywordStyle[1] = contents
            end
        end
    end
    return self.keywordStyle
end

function LetterStyleMergeModule:isKeywordEnabled()
    return self.rawKeywordStyleStr ~= nil
end

function LetterStyleMergeModule:applyTextStyle(_sticker)
    local function isJson(str)
        return str ~= nil and #str >=2 and str:sub(1,1) == "{"
    end
    
    local function _removeAbsoluteKeywordSize(keyword_rich_text_str)
        if isJson(keyword_rich_text_str) then
            local keyword_rich_text = cjson.decode(keyword_rich_text_str)
            if keyword_rich_text and keyword_rich_text.styles and keyword_rich_text.styles[1] and keyword_rich_text.styles[1].size ~= nil then
                keyword_rich_text.styles[1].size = nil
                return cjson.encode(keyword_rich_text)
            end
        end
        return keyword_rich_text_str
    end

    local sticker = nil
    if _sticker == nil then
        sticker = self.sticker
    else
        sticker = _sticker
    end
    if Common.isEditor then
        return
    end

    if self.rawKeywordStyleStr and self.rawCaptionStr then
        local captionInfo = cjson.decode(self.rawCaptionStr)
        local words = captionInfo.words
        if sticker.richText.applyTextStyle then
            local keywordStyleStr = {}
            local contents = cjson.decode(self.rawKeywordStyleStr)

            if type(contents) == "table" then
                if #contents > 0 then
                    for _, style in ipairs(contents) do
                        table.insert(keywordStyleStr, cjson.encode(style))
                    end
                else
                    table.insert(keywordStyleStr, self.rawKeywordStyleStr)
                end
            end

            if #keywordStyleStr > 0 then
                local range = {}
                local count = #keywordStyleStr
                for i = 1, count do
                    range[i] = Amaz.Vector()
                end
                local curRange = 0
                local curKeywordIndex = 1
                for i = 1, #words do
                    local word = words[i]
                    if word.is_key and (Common.isLegalStr(word.text)) then
                        local index = (curKeywordIndex - 1) % count + 1
                        range[index]:pushBack(curRange)
                        range[index]:pushBack(curRange + Common.getLetterCount(word.text))
                        curKeywordIndex = curKeywordIndex + 1
                    end
                    curRange = curRange + Common.getLetterCount(word.text)
                end
                for i = 1, count do
                    if range[i]:size() > 0 then
                        local style = keywordStyleStr[i]
                        if self.relative then
                            style = _removeAbsoluteKeywordSize(style)
                        end
                        sticker.richText:applyTextStyle(style, range[i])
                    end
                end
            end
        end
    end
end

function LetterStyleMergeModule:onSetProperty(key, value)
    if key == "keyword_rich_text" and value ~= "" then
        Amaz.LOGE("lrc keyword_rich_text", value)
        self.rawKeywordStyleStr = value
    end

    if key == "caption_duration_info" and value ~= "" then
        Amaz.LOGE("lrc caption_duration_info", value)
        self.rawCaptionStr = value
    end
end

function LetterStyleMergeModule:reset()
end

return LetterStyleMergeModule
