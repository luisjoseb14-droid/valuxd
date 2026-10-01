--[[
    Script Name: CaptionModule.lua
    Version: 3.6
    Update Date: 2024.01.20
--]]
--[[  ****************************************
    Common Func
--    **************************************** ]]

local Common = {
    sdfText = nil,
    isEditor = (Amaz.Macros and Amaz.Macros.EditorSDK) and true or false,
    STICKER = nil,
    mergeBlendMode = nil,
    earlierbrushWord = false,
    superSize = 1,
    WORD_STATE = {
        READING = 0,
        BEFORE_READ = 1,
        AFTER_READ = 2
    },
    LINE_STATE = {
        READING = 0,
        BEFORE_READ = 1,
        AFTER_READ = 2
    },
    captionKeywordStyle = nil,
    getTightRect = function(letter, outlineMaxWidth, expandAffector)
        local pixelHeight = letter.letterStyle.fontSize * 300 / 72
        local rectDistance = pixelHeight * outlineMaxWidth
        local expand = expandAffector == nil and 0.2 or expandAffector
        local tightRect = Amaz.Rect(
            letter.rect.x + rectDistance,
            letter.rect.y + rectDistance,
            letter.rect.width - rectDistance * 2 + expand * pixelHeight,
            letter.rect.height - rectDistance * 2 + expand * pixelHeight
        )
        return tightRect
    end,

    readStrFromFile = function(file_path)
        local file = io.input(file_path)
        local text = io.read("*a")
        return text
    end,

    remap01 = function(a, b, x)
        if x < a then return 0 end
        if x > b then return 1 end
        return (x - a) / (b - a)
    end,

    mix = function(a, b, x)
        return a * (1 - x) + b * x
    end,

    clamp = function(x, a, b)
        return math.max(math.min(x, b), a)
    end,

    getLetterCount = function(_str)
        if sdfText == nil then
            sdfText = Amaz.SDFText()
        end
        sdfText.str = _str
        local size = sdfText.chars:size()
        sdfText.str = ""
        return size

        -- local str = _str
        -- local lenInByte = #str
        -- local count = 0
        -- local i = 1
        -- while true do
        --     local curByte = string.byte(str, i)
        --     if i > lenInByte then
        --         break
        --     end
        --     local byteCount = 1
        --     if curByte > 0 and curByte < 128 then
        --         byteCount = 1
        --     elseif curByte >= 128 and curByte < 224 then
        --         byteCount = 2
        --     elseif curByte >= 224 and curByte < 240 then
        --         byteCount = 3
        --     elseif curByte >= 240 and curByte <= 247 then
        --         byteCount = 4
        --     else
        --         break
        --     end
        --     -- local char = string.sub(str, i, i+byteCount-1)
        --     i = i + byteCount
        --     count = count + 1
        -- end
        -- return count
    end,

    isLegalStr = function(_str)
        local ilegal = _str == " " or _str == "\n"
        return not ilegal
    end,

    getTimeRange = function(_words)
        local startTime = 999999
        local endTime = 0
        for i = 1, #_words do
            local w = _words[i]
            if w.text ~= " " and w.text ~= "\n" then
                local st = w.pack_start_time == nil and w.start_time or w.pack_start_time
                local et = w.pack_end_time == nil and w.end_time or w.pack_end_time
                startTime = startTime == nil and st or math.min(startTime, st)
                endTime = endTime == nil and et or math.max(endTime, et)
            end
        end
        return startTime * 0.001, endTime * 0.001
    end,

    register = function(_obj, _name, _default, _getter, _setter)
        _obj[_name] = _default

        local funcName = _name:gsub("^%l", string.upper)
        local getFuncName = "get" .. funcName
        local setFuncName = "set" .. funcName

        if _getter then
            _obj[getFuncName] = _getter
        else
            if _obj[getFuncName] == nil then
                _obj[getFuncName] = function(_o)
                    return _o[_name]
                end
            end
        end

        if _setter and _obj[setFuncName] == nil then
            _obj[setFuncName] = _setter
        else
            if _obj[setFuncName] == nil then
                _obj[setFuncName] = function(_o, _val)
                    _o[_name] = _val
                end
            end
        end
    end,

    flushCmd = function(sticker)
        -- flush cmd based on oriStr
        if sticker then
            sticker.richText.str = sticker.oriStr
            sticker.richText:forceTypeSetting()
            if sticker.richText.forceFlushCommandQueue then
                sticker.richText:forceFlushCommandQueue()
            end
        end
    end,

    fakeDataForKeyWordMerge = {
        -- letterColorRGBA = Amaz.Color(0.5, 1, 0.5, 1),
        fontSize = 30
    },

    fakeMergeFunc = function(letter, fakeData)
        if fakeData.letterColorRGBA then
            letter.letterStyle.letterColorRGBA = fakeData.letterColorRGBA
        end
        if fakeData.fontSize then
            letter.letterStyle.fontSize = fakeData.fontSize
        end
    end,

}

local mergeModule = nil

local json = cjson.new()

--[[  ****************************************
        CWord
    --    **************************************** ]]
local CWord = {}
CWord.__index = CWord

function CWord.new(_wordInfo, _page, _line)
    local self = setmetatable({}, CWord)


    self.progress = 0
    self.oriLetters = {}
    Common.register(self, "page", _page)
    Common.register(self, "line", _line)

    Common.register(self, "startTime", _wordInfo.pack_start_time * 0.001)
    Common.register(self, "endTime", _wordInfo.pack_end_time * 0.001)

    Common.register(self, "packStartTime", _wordInfo.pack_start_time * 0.001)
    Common.register(self, "packEndTime", _wordInfo.pack_end_time * 0.001)


    Common.register(self, "str", _wordInfo.text)
    Common.register(self, "idx", _wordInfo.idx)
    Common.register(self, "legalIdx", _wordInfo.legal_idx)

    Common.register(self, "idxInPage", -1)
    Common.register(self, "legalIdxInPage", -1)

    Common.register(self, "idxInLine", -1)
    Common.register(self, "legalIdxInLine", -1)

    Common.register(self, "isKey", _wordInfo.is_key)
    Common.register(self, "keywordIdx", _wordInfo.keyword_idx)
    Common.register(self, "startLetterIdx", _wordInfo.ori_start_letter_idx)
    -- Common.register(self, "letterIdxOffset", 0)

    Common.register(self, "letters", {})
    Common.register(self, "oriLetters", {})
    Common.register(self, "letterCount", 0,
        function()
            return #self.letters
        end,
        nil
    )

    Common.register(self, "progress", 0)
    Common.register(self, "duration", 0)

    -- animations
    self.animingFuncs = {
        [Common.WORD_STATE.READING] = nil,
        [Common.WORD_STATE.BEFORE_READ] = nil,
        [Common.WORD_STATE.AFTER_READ] = nil,
    }

    self.animingEarlierFuncs = {
        [Common.WORD_STATE.READING] = nil,
        [Common.WORD_STATE.BEFORE_READ] = nil,
        [Common.WORD_STATE.AFTER_READ] = nil,
    }
    return self
end

function CWord:setNextWord(_other)
    self.nextWord = _other
end

function CWord:getNextWord()
    local closeTo = false
    if self.nextWord and (math.abs(self.nextWord:getStartTime() - self:getEndTime()) < 0.001) then
        closeTo = true
    end
    return self.nextWord, closeTo
end

function CWord:setLastWord(_other)
    self.lastWord = _other
end

function CWord:getLastWord()
    local closeTo = false
    if self.lastWord and (math.abs(self.lastWord:getStartTime() - self:getEndTime()) < 0.001) then
        closeTo = true
    end
    return self.lastWord, closeTo
end

function CWord:getProgress(_time)
    return Common.clamp((_time - self.startTime) / (self.endTime - self.startTime), 0, 1)
end

function CWord:getDuration()
    return self.endTime - self.startTime
end

function CWord:isLegal()
    return self.legalIdx > 0
end

function CWord:getInitalRect()
    return self:getRect(function(_l)
        return _l.initialPosition
    end)
end

function CWord:getRect(_posDelegate)
    if self.letters == nil then
        return Amaz.Rect(0, 0, 0, 0)
    end
    -- local mgdLetters = self.oriLetters
    local baseLetters = self.letters

    local function getWordRect(_letters)
        local ldp = nil
        local urp = nil
        for i = 1, #_letters do
            local let = _letters[i]
            if Common.isLegalStr(let.utf8) == true then
                local rect = Common.getTightRect(let, Common.STICKER.richText.outlineMaxWidth)
                local pos = _posDelegate == nil and let.position or _posDelegate(let)
                if ldp == nil then
                    ldp = {
                        pos.x - rect.width * 0.5,
                        pos.y - rect.height * 0.5,
                    }
                else
                    ldp = {
                        math.min(pos.x - rect.width * 0.5, ldp[1]),
                        math.min(pos.y - rect.height * 0.5, ldp[2]),
                    }
                end

                if urp == nil then
                    urp = {
                        pos.x + rect.width * 0.5,
                        pos.y + rect.height * 0.5,
                    }
                else
                    urp = {
                        math.max(pos.x + rect.width * 0.5, urp[1]),
                        math.max(pos.y + rect.height * 0.5, urp[2]),
                    }
                end
            end
        end
        if ldp == nil then
            return Amaz.Rect(0, 0, 0, 0)
        end
        local rect = Amaz.Rect(ldp[1], ldp[2], urp[1] - ldp[1], urp[2] - ldp[2])
        return rect
    end

    -- local mgdRect = getWordRect(mgdLetters)
    local baseRect = getWordRect(baseLetters)
    return baseRect
end

function CWord:getInitialCenter()
    return self:getCenter(function(_l)
        return _l.initialPosition
    end)
end

function CWord:getCenter(_centerDelegate)
    if self.letters == nil then
        return Amaz.Vector2f(-1, -1)
    end

    local rect = self:getRect(_centerDelegate)
    local center = Amaz.Vector2f(rect.x + rect.width * 0.5, rect.y + rect.height * 0.5)
    return center
end

function CWord:setReadingAnim(_func, _isEarlier)
    if _isEarlier == true then
        self.animingEarlierFuncs[Common.WORD_STATE.READING] = _func
    else
        self.animingFuncs[Common.WORD_STATE.READING] = _func
    end
end

function CWord:setAfterReadAnim(_func, _isEarlier)
    if _isEarlier == true then
        self.animingEarlierFuncs[Common.WORD_STATE.AFTER_READ] = _func
    else
        self.animingFuncs[Common.WORD_STATE.AFTER_READ] = _func
    end
end

function CWord:setBeforeReadAnim(_func, _isEarlier)
    if _isEarlier == true then
        self.animingEarlierFuncs[Common.WORD_STATE.BEFORE_READ] = _func
    else
        self.animingFuncs[Common.WORD_STATE.BEFORE_READ] = _func
    end
end

function CWord:getState(_time)
    local state = nil
    if _time < self.startTime then
        state = Common.WORD_STATE.BEFORE_READ
    elseif _time >= self.startTime and _time < self.endTime then
        state = Common.WORD_STATE.READING
    elseif _time >= self.endTime then
        state = Common.WORD_STATE.AFTER_READ
    end
    return state
end

function CWord:setState(_val)
    self.state = _val
end

function CWord:hasWholeAnimDelegate(_isEarlier)
    if _isEarlier == true then
        return self.animingEarlierFuncs[Common.WORD_STATE.BEFORE_READ] and
            self.animingEarlierFuncs[Common.WORD_STATE.READING] and
            self.animingEarlierFuncs[Common.WORD_STATE.AFTER_READ]
    end
    return self.animingFuncs[Common.WORD_STATE.BEFORE_READ] and
        self.animingFuncs[Common.WORD_STATE.READING] and
        self.animingFuncs[Common.WORD_STATE.AFTER_READ]
end

function CWord:animing(_time)
    if self:isLegal() == false then
        return
    end

    if self:hasWholeAnimDelegate() then
        local p = self:getProgress(_time)
        self.state = self:getState(_time)

        if self.animingFuncs[self.state] then
            self.animingFuncs[self.state](self, p, _time)
        end
    end
end

function CWord:animingEarlier(_time)
    if self:isLegal() == false then
        return
    end

    if self:hasWholeAnimDelegate(true) then
        local p = self:getProgress(_time)
        self.state = self:getState(_time)

        if self.animingEarlierFuncs[self.state] then
            self.animingEarlierFuncs[self.state](self, p, _time)
        end
    end
end

function CWord:brushWord()
    if self:getIsKey() then
        if mergeModule then
            local keywordIdx = self:getKeywordIdx()
            for i = 1, #self.letters do
                mergeModule:merge(self.letters[i], self.oriLetters[i], keywordIdx, Common.mergeBlendMode)
            end
        end
    else
        for i = 1, #self.letters do
            self.letters[i].utf8 = self.oriLetters[i].utf8
        end
    end
end

function CWord:setAbsAnchor(_anchor)
    if self:isLegal() then
        for i = 1, #self.letters do
            local l = self.letters[i]
            l.anchor = Amaz.Vector2f(
                _anchor.x - l.initialPosition.x,
                _anchor.y - l.initialPosition.y
            )
        end
    end
end

function CWord:setAnchor(_anchor)
    local rect = self:getRect()
    local center = self:getCenter()
    for i = 1, #self.letters do
        local letter = self.letters[i]

        local lx = center.x - letter.position.x
        local ly = center.y - letter.position.y
        lx = lx + _anchor.x * rect.width * 0.5
        ly = ly + _anchor.y * rect.height * 0.5
        letter.anchor = Amaz.Vector2f(lx, ly)
    end
end

function CWord:destroy()
    self.letters = {}
    self.page = nil
    self.line = nil
end

function CWord:addExtraChars(_chars, _isAfter)
    if self:isLegal() == false or #self.letters <= 0 then
        return
    end
    if _isAfter == nil then
        _isAfter = false
    end
    if type(_chars) == "string" then
        _chars = { _chars }
    end
    local beforeStr = ""
    local cloneIdx = 1
    local letter = self.letters[cloneIdx]
    local oriLetter = self.oriLetters[cloneIdx]
    if _isAfter == true then
        cloneIdx = #self.letters + 1
        letter = self.letters[cloneIdx - 1]
        oriLetter = self.oriLetters[cloneIdx - 1]
    end
    for i = #_chars, 1, -1 do
        local char = _chars[i]
        local l = letter:clone()
        local oriL = oriLetter:clone()
        l.utf8 = char
        oriL.utf8 = char
        table.insert(self.letters, cloneIdx, l)
        table.insert(self.oriLetters, cloneIdx, oriL)
        beforeStr = char .. beforeStr
    end
    if _isAfter == true then
        self.str = self.str .. beforeStr
    else
        self.str = beforeStr .. self.str
    end
end


function CWord:switchCase(_case)
    if _case == nil then
        return
    end

    local function capitalizeFirstLetter(str, local_index)
        return string.upper(string.sub(str, 1, local_index)) .. string.sub(str, local_index + 1)
    end

    if _case == 1 then
        self.str = string.upper(self.str)
        for i = 1, #self.letters do
            local l = self.letters[i]
            local ori_l = self.oriLetters[i]
            l.utf8 = string.upper(l.utf8)
            ori_l.utf8 = string.upper(ori_l.utf8)
        end
    elseif _case == 2 then
        self.str = string.lower(self.str)
        for i = 1, #self.letters do
            local l = self.letters[i]
            local ori_l = self.oriLetters[i]
            l.utf8 = string.lower(l.utf8)
            ori_l.utf8 = string.lower(ori_l.utf8)
        end
    elseif _case == 3 then
        if #self.letters > 0 then
            local l = self.letters[1]
            local ori_l = self.oriLetters[1]
            capitalizeFirstLetter(self.str, #l.utf8)
            l.utf8 = l.utf8:upper()
            ori_l.utf8 = string.upper(ori_l.utf8)
        end
    end
end

--[[  ****************************************
        CLine: manager all the CWord
    --    **************************************** ]]
local CLine = {}
CLine.__index = CLine

function CLine.new(_idx, _page)
    local self = setmetatable({}, CLine)

    self.progress = 0
    self.duration = 0
    Common.register(self, "page", _page)
    Common.register(self, "words", {})
    Common.register(self, "idx", _idx)
    Common.register(self, "idxInPage", -1)
    Common.register(self, "letters", {})
    Common.register(self, "str", "")

    Common.register(self, "startTime", 0)
    Common.register(self, "endTime", 0)
    Common.register(self, "forcePage", false)

    -- animations
    self.animingFuncs = {
        [Common.LINE_STATE.READING] = nil,
        [Common.LINE_STATE.BEFORE_READ] = nil,
        [Common.LINE_STATE.AFTER_READ] = nil,
    }

    self.animingEarlierFuncs = {
        [Common.LINE_STATE.READING] = nil,
        [Common.LINE_STATE.BEFORE_READ] = nil,
        [Common.LINE_STATE.AFTER_READ] = nil,
    }
    return self
end

function CLine:_replaceSpaces()
    -- test if letter.actionType is defined (from EffectSDK 1830)
    if Amaz.Letter().actionType == nil then
        return
    end
    -- set leading whitespaces invisible
    local stop = false
    for i=1, #self.words do
        local word = self.words[i]
        for j=1, #word.letters do
            local letter = word.letters[j]
            local oriLetter = word.oriLetters[j]
            if letter.utf8 == '\n' or letter.utf8 == ' ' then
                letter.actionType = 1
                oriLetter.actionType = 1
            else
                stop = true
                break
            end
        end
        if stop then break end
    end

    -- set trailiing whitespaces invisible
    stop = false
    for i=#self.words, 1, -1 do
        local word = self.words[i]
        for j=#word.letters, 1, -1 do
            local letter = word.letters[j]
            local oriLetter = word.oriLetters[j]
            if letter.utf8 == '\n' or letter.utf8 == ' ' then
                letter.actionType = 1
                oriLetter.actionType = 1
            else
                stop = true
                break
            end
        end
        if stop then break end
    end
end

function CLine:setExtraFontSizeScale(_scale)
    local fsScale = _scale
    Amaz.LOGI("lrc cline /" .. tostring(self:getStr()), _scale)

    for i = 1, #self.words do
        local word = self.words[i]
        local letters = word:getLetters()
        local oriLetters = word:getOriLetters()
        -- Amaz.LOGE("lrc letters", #letters)
        for j = 1, #letters do
            local letter = letters[j]
            -- Amaz.LOGW("lrc letter "..tostring(letter.utf8), tostring(letter.letterStyle.fontSize) )
            letter.letterStyle.fontSize = oriLetters[j].letterStyle.fontSize * fsScale
        end
    end
end

function CLine:isLegal()
    return #self.words > 0
end

function CLine:getProgress(_time)
    return Common.clamp((_time - self.startTime) / (self.endTime - self.startTime), 0, 1)
end

function CLine:getDuration()
    return self.endTime - self.startTime
end

function CLine:isReading(_time)
    if self:getIdx() == 1 then
        return _time >= self.startTime and _time <= self.endTime
    end
    return _time > self.startTime and _time <= self.endTime
end

function CLine:addWord(_word)
    table.insert(self.words, _word)
end

function CLine:getLegalWords()
    if self.legalWords == nil then
        self.legalWords = {}
        for i = 1, #self.words do
            local w = self.words[i]
            if w:isLegal() then
                table.insert(self.legalWords, w)
            end
        end
    end
    return self.legalWords
end


function CLine:setPage(page)
    self.page = page
    for i = 1, #self.words do
        local word = self.words[i]
        word:setPage(page)
    end
end

function CLine:getLegalWordCount()
    if not self:isLegal() then
        return 0
    end
    local count = 0
    for i = 1, #self.words do
        local w = self.words[i]
        if w:isLegal() then
            count = count + 1
        end
    end
    return count
end

function CLine:getWordCount()
    if not self:isLegal() then
        return 0
    end
    return #self.words
end

function CLine:getLetterCount()
    if not self:isLegal() then
        return 0
    end
    local count = 0
    for i = 1, #self.words do
        local w = self.words[i]
        count = count + w:getLetterCount()
    end
    return count
end

function CLine:getLegalLetterCount()
    if not self:isLegal() then
        return 0
    end
    local count = 0
    for i = 1, #self.words do
        local w = self.words[i]
        if w:isLegal() then
            count = count + w:getLetterCount()
        end
    end
    return count
end

function CLine:getOriStartLetterIdx()
    if self:isLegal() then
        return self.words[1]:getStartLetterIdx()
    else
        return -1
    end
end

function CLine:getState(_time)
    local state = nil
    if _time < self.startTime then
        state = Common.LINE_STATE.BEFORE_READ
    elseif _time >= self.startTime and _time < self.endTime then
        state = Common.LINE_STATE.READING
    elseif _time >= self.endTime then
        state = Common.LINE_STATE.AFTER_READ
    end
    return state
end

function CLine:hasWholeAnimDelegate(_isEarlier)
    if _isEarlier == true then
        return self.animingEarlierFuncs[Common.LINE_STATE.BEFORE_READ] and
            self.animingEarlierFuncs[Common.LINE_STATE.READING] and
            self.animingEarlierFuncs[Common.LINE_STATE.AFTER_READ]
    end
    return self.animingFuncs[Common.LINE_STATE.BEFORE_READ] and
        self.animingFuncs[Common.LINE_STATE.READING] and
        self.animingFuncs[Common.LINE_STATE.AFTER_READ]
end

function CLine:animing(_time)
    if self:isLegal() == false then
        return
    end

    if self:hasWholeAnimDelegate() then
        local p = self:getProgress(_time)
        local state = self:getState(_time)

        if self.animingFuncs[state] then
            self.animingFuncs[state](self, p, _time)
        end
    end
end

function CLine:animingEarlier(_time)
    if self:isLegal() == false then
        return
    end

    if self:hasWholeAnimDelegate(true) then
        local p = self:getProgress(_time)
        local state = self:getState(_time)

        if self.animingEarlierFuncs[state] then
            self.animingEarlierFuncs[state](self, p, _time)
        end
    end
end

function CLine:setReadingAnim(_func, _isEarlier)
    if _isEarlier == true then
        self.animingEarlierFuncs[Common.LINE_STATE.READING] = _func
    else
        self.animingFuncs[Common.LINE_STATE.READING] = _func
    end
end

function CLine:setAfterReadAnim(_func, _isEarlier)
    if _isEarlier == true then
        self.animingEarlierFuncs[Common.LINE_STATE.AFTER_READ] = _func
    else
        self.animingFuncs[Common.LINE_STATE.AFTER_READ] = _func
    end
end

function CLine:setBeforeReadAnim(_func, _isEarlier)
    if _isEarlier == true then
        self.animingEarlierFuncs[Common.LINE_STATE.BEFORE_READ] = _func
    else
        self.animingFuncs[Common.LINE_STATE.BEFORE_READ] = _func
    end
end


function CLine:refresh()
    self.str = ""
    self.letters = {}
    local curLegalWordIdx = 0
    for i = 1, #self.words do
        local word = self.words[i]

        word:setIdxInLine(i)
        word:setPage(self:getPage())
        if word:isLegal() then
            curLegalWordIdx = curLegalWordIdx + 1
            word:setLegalIdxInLine(curLegalWordIdx)
        end

        local letters = word:getLetters()
        for j = 1, #letters do
            table.insert(self.letters, letters[j])
        end

        self.str = self.str .. word:getStr()
    end

    self.startTime = self.words[1]:getStartTime()
    self.endTime = self.words[#self.words]:getEndTime()
end

function CLine:getInitalRect()
    return self:getRect(function(_l)
        return _l.initialPosition
    end)
end

function CLine:getRect(_posDelegate)
    if self:isLegal() == false then
        return Amaz.Rect(0, 0, 0, 0)
    end

    local leftDownPoint = nil
    local rightUpPoint = nil
    for i = 1, #self.words do
        local word = self.words[i]
        if word:isLegal() then
            local rect = word:getRect(_posDelegate)
            local curLeftDownPoint = { rect.x, rect.y }
            local curRightUpPoint = { rect.x + rect.width, rect.y + rect.height }
            if leftDownPoint == nil then
                leftDownPoint = curLeftDownPoint
            else
                leftDownPoint = {
                    math.min(leftDownPoint[1], curLeftDownPoint[1]),
                    math.min(leftDownPoint[2], curLeftDownPoint[2]),
                }
            end

            if rightUpPoint == nil then
                rightUpPoint = curRightUpPoint
            else
                rightUpPoint = {
                    math.max(rightUpPoint[1], curRightUpPoint[1]),
                    math.max(rightUpPoint[2], curRightUpPoint[2]),
                }
            end
        end
    end

    if leftDownPoint and rightUpPoint then
        local width = rightUpPoint[1] - leftDownPoint[1]
        local height = rightUpPoint[2] - leftDownPoint[2]
        return Amaz.Rect(leftDownPoint[1], leftDownPoint[2],
            width, height)
    end
    return Amaz.Rect(0, 0, 0, 0)
end

function CLine:getInitialCenter()
    return self:getCenter(function(_l)
        return _l.initialPosition
    end)
end

function CLine:getCenter(_centerDelegate)
    if self:isLegal() == false then
        return Amaz.Vector2f(-1, -1)
    end

    local rect = self:getRect(_centerDelegate)
    local center = Amaz.Vector2f(rect.x + rect.width * 0.5, rect.y + rect.height * 0.5)
    return center
end

function CLine:setAnchor(_anchor)
    if self:isLegal() then
        local rect = self:getRect()
        local anchor = Amaz.Vector2f(_anchor.x * 0.5 + 0.5, _anchor.y * 0.5 + 0.5)
        anchor = Amaz.Vector2f(
            rect.x + anchor.x * rect.width,
            rect.y + anchor.y * rect.height
        )
        for i = 1, #self.words do
            local word = self.words[i]
            word:setAbsAnchor(anchor)
        end
    end
end

--[[  ****************************************
        CPage: manager all the CWord/CLine
    --    **************************************** ]]
local CPage = {}
CPage.__index = CPage

function CPage.new(_idx)
    local self = setmetatable({}, CPage)

    self.oriStartLetterIdx = -1
    self.letterCount = -1
    Common.register(self, "words", {})
    Common.register(self, "lines", {})
    Common.register(self, "str", "")
    Common.register(self, "idx", _idx)
    Common.register(self, "letters", {})
    Common.register(self, "startTime", 0)
    Common.register(self, "endTime", 0)

    Common.register(self, "progress", 0)
    Common.register(self, "duration", 0)
    Common.register(self, "startLetterIdx", -1)

    Common.register(self, "enable", true)

    -- for fit with max line
    Common.register(self, "fitMaxLine", false)
    Common.register(self, "extraLineSpacing", 0)
    Common.register(self, "oriLineSpacing", 0)
    Common.register(self, "lastLineMaxScale", 1.3)
    Common.register(self, "lastLineWidthLimitFactor", 0.4)

    return self
end

function CPage:_setMaxLineFitable()
    -- Amaz.LOGI("lrc page ", tostring(self.fitMaxLine))
    if self.fitMaxLine == true and #self.lines > 0 then
        local maxLineScale = 1
        local maxWidth = -1
        local rectWidths = {}

        local maxWordCount = -1
        for i = 1, #self.lines do
            local line = self.lines[i]
            local curRect = line:getRect()
            maxWidth = math.max(curRect.width, maxWidth)
            table.insert(rectWidths, curRect.width)
            maxWordCount = math.max(maxWordCount, line:getWordCount())
        end

        for i = 1, #self.lines do
            local line = self.lines[i]
            local scale = maxWidth / rectWidths[i]

            -- if i == #self.lines and (maxWordCount * 0.55 > line:getWordCount()) then
            --     scale = math.min(scale, 1.2)
            -- end

            if i == #self.lines and (rectWidths[i] < maxWidth * self.lastLineWidthLimitFactor) then
                scale = math.min(scale, self.lastLineMaxScale)
            end

            maxLineScale = math.max(maxLineScale, scale)
            line:setExtraFontSizeScale(scale)
        end

        Common.STICKER.richText.typeSettingParam.lineSpacing = self.oriLineSpacing +
            self.extraLineSpacing * (1. / maxLineScale)
    end
end

function CPage:setAnchor(_anchor)
    if self:isLegal() then
        local rect = self:getRect()
        local anchor = Amaz.Vector2f(_anchor.x * 0.5 + 0.5, _anchor.y * 0.5 + 0.5)
        anchor = Amaz.Vector2f(
            rect.x + anchor.x * rect.width,
            rect.y + anchor.y * rect.height
        )
        for i = 1, #self.words do
            local word = self.words[i]
            word:setAbsAnchor(anchor)
        end
    end
end

function CPage:getLegalWordCount()
    if not self:isLegal() then
        return 0
    end
    local count = 0
    for i = 1, #self.words do
        local w = self.words[i]
        if w:isLegal() then
            count = count + 1
        end
    end
    return count
end

function CPage:getWordCount()
    if not self:isLegal() then
        return 0
    end
    return #self.words
end

function CPage:getLetterCount()
    if not self:isLegal() then
        return 0
    end
    local count = 0
    for i = 1, #self.words do
        local w = self.words[i]
        count = count + w:getLetterCount()
    end
    return count
end

function CPage:getLegalLetterCount()
    if not self:isLegal() then
        return 0
    end
    local count = 0
    for i = 1, #self.words do
        local w = self.words[i]
        if w:isLegal() then
            count = count + w:getLetterCount()
        end
    end
    return count
end

function CPage:getOriStartLetterIdx()
    if self:isLegal() then
        return self.words[1]:getStartLetterIdx()
    else
        return -1
    end
end

function CPage:getProgress(_time)
    return Common.clamp((_time - self.startTime) / (self.endTime - self.startTime), 0, 1)
end

function CPage:isReading(_time)
    if self:getIdx() == 1 then
        return _time >= self.startTime and _time <= self.endTime
    end
    return _time > self.startTime and _time <= self.endTime
end

function CPage:addWord(_word)
    table.insert(self.words, _word)
end

function CPage:addLine(_line)
    table.insert(self.lines, _line)
end

function CPage:getInitalRect()
    return self:getRect(function(_l)
        return _l.initialPosition
    end)
end

function CPage:getRect(_posDelegate)
    if self:isLegal() == false then
        return nil
    end

    local leftDownPoint = nil
    local rightUpPoint = nil
    for i = 1, #self.words do
        local word = self.words[i]
        if word:isLegal() then
            local rect = word:getRect(_posDelegate)
            local curLeftDownPoint = { rect.x, rect.y }
            local curRightUpPoint = { rect.x + rect.width, rect.y + rect.height }
            if leftDownPoint == nil then
                leftDownPoint = curLeftDownPoint
            else
                leftDownPoint = {
                    math.min(leftDownPoint[1], curLeftDownPoint[1]),
                    math.min(leftDownPoint[2], curLeftDownPoint[2]),
                }
            end

            if rightUpPoint == nil then
                rightUpPoint = curRightUpPoint
            else
                rightUpPoint = {
                    math.max(rightUpPoint[1], curRightUpPoint[1]),
                    math.max(rightUpPoint[2], curRightUpPoint[2]),
                }
            end
        end
    end

    if leftDownPoint and rightUpPoint then
        return Amaz.Rect(leftDownPoint[1], leftDownPoint[2],
            rightUpPoint[1] - leftDownPoint[1], rightUpPoint[2] - leftDownPoint[2])
    end
    return nil
end

function CPage:getRectPerLine(_posDelegate)
    if self:isLegal() == false then
        return nil
    end

    local lineSplit = {}
    local letters = self:getLetters()
    local lastRowth = -1
    local line = {}
    for i = 1, #letters do
        local let = letters[i]
        if lastRowth == -1 or lastRowth ~= let.rowth then
            if #line > 0 then
                table.insert(lineSplit, line)
            end
            line = {}
            lastRowth = let.rowth
        end
        table.insert(line, let)
    end

    if #line > 0 then
        table.insert(lineSplit, line)
    end

    local function getLettersRect(_letters)
        local ldp = nil
        local urp = nil
        for i = 1, #_letters do
            local let = _letters[i]
            if Common.isLegalStr(let.utf8) == true then
                local rect = Common.getTightRect(let, Common.STICKER.richText.outlineMaxWidth)
                local pos = _posDelegate == nil and let.position or _posDelegate(let)
                if ldp == nil then
                    ldp = {
                        pos.x - rect.width * 0.5,
                        pos.y - rect.height * 0.5,
                    }
                else
                    ldp = {
                        math.min(pos.x - rect.width * 0.5, ldp[1]),
                        math.min(pos.y - rect.height * 0.5, ldp[2]),
                    }
                end

                if urp == nil then
                    urp = {
                        pos.x + rect.width * 0.5,
                        pos.y + rect.height * 0.5,
                    }
                else
                    urp = {
                        math.max(pos.x + rect.width * 0.5, urp[1]),
                        math.max(pos.y + rect.height * 0.5, urp[2]),
                    }
                end
            end
        end
        if ldp == nil then
            return Amaz.Rect(0, 0, 0, 0)
        end
        local rect = Amaz.Rect(ldp[1], ldp[2], urp[1] - ldp[1], urp[2] - ldp[2])
        return rect
    end

    local lineRect = {}
    for i = 1, #lineSplit do
        local line = lineSplit[i]
        local rect = getLettersRect(line)
        table.insert(lineRect, rect)
    end
    return lineRect
end

function CPage:getOriRect(_posDelegate)
    if self.oriRect == nil then
        self.oriRect = self:getRect(_posDelegate)
    end
    return self.oriRect
end


function CPage:getLegalWords()
    if self.legalWords == nil then
        self.legalWords = {}
        for i = 1, #self.words do
            local w = self.words[i]
            if w:isLegal() then
                table.insert(self.legalWords, w)
            end
        end
    end
    return self.legalWords
end

function CPage:refresh()
    if not self:isLegal() then
        return
    end

    local function _syncWords()
        local curLegalWordCount = 0
        for i = 1, #self.words do
            local word = self.words[i]
            word:setIdxInPage(i)

            if word:isLegal() then
                curLegalWordCount = curLegalWordCount + 1
                word:setLegalIdxInPage(curLegalWordCount)
            end

            local letters = word:getLetters()
            for j = 1, #letters do
                table.insert(self.letters, letters[j])
            end

            if i == #self.words then
                word:setNextWord(nil)
            end

            if i == #self.words then
                word:setLastWord(nil)
            end
        end
    end

    self.str = ""
    self.letters = {}
    -- Amaz.LOGE("lrc line count 123", tostring(#self.lines))
    if #self.lines > 0 then
        self.words = {}

        for i = 1, #self.lines do
            local line = self.lines[i]
            line:setIdxInPage(i)
            line:refresh()
            self.str = self.str .. line:getStr()

            if i ~= #self.lines then
                self.str = self.str .. "\n"
            end

            local words = line:getWords()
            for j = 1, #words do
                local word = words[j]
                table.insert(self.words, word)
            end
        end

        _syncWords()
    else
        for i = 1, #self.words do
            local word = self.words[i]
            self.str = self.str .. word:getStr()
        end

        _syncWords()
    end
    -- Amaz.LOGI("lrc test " .. tostring(self:getIdx()), tostring(self.str))
    self:_setMaxLineFitable()

    self.startTime = self.words[1]:getStartTime()
    self.endTime = self.words[#self.words]:getEndTime()
end

function CPage:getDuration()
    if self:isLegal() then
        return self.endTime - self.startTime
    end
    return -1
end

function CPage:_syncStr()
    Common.flushCmd(Common.STICKER)
    Common.STICKER.richText.str = self:getStr()
    Common.STICKER.richText:forceTypeSetting()
end

-- if #self.lines == 0, there is no need to replace spaces because the spaces are given by users, instead of being generated by programs
function CPage:_replaceSpaces()
    for i = 1, #self.lines do
        self.lines[i]:_replaceSpaces()
    end
    self:refresh()
end

function CPage:_syncLetters()
    local curLetters = Amaz.Vector()
    local curIdx = 0
    if #self.lines > 0 then
        for i = 1, #self.lines do
            local line = self.lines[i]
            local words = line:getWords()
            for j = 1, #words do
                local word = words[j]
                local letters = word:getLetters()
                local oriLetters = word:getOriLetters()
                -- word:setLetterIdxOffset(i - 1)
                for k = 1, #letters do
                    local letter = letters[k]
                    letter.letterStyle.fontSize = oriLetters[k].letterStyle.fontSize
                    curLetters:pushBack(letter)
                    curIdx = curIdx + 1
                end
            end

            if i ~= #self.lines then
                local letter = Amaz.Letter()
                letter.utf8 = "\n"
                letter.letterStyle.fontSize = 0
                curLetters:pushBack(letter)
            end
        end
    else
        for i = 1, #self.words do
            local word = self.words[i]
            local letters = word:getLetters()
            local oriLetters = word:getOriLetters()
            for j = 1, #letters do
                letters[j].letterStyle.fontSize = oriLetters[j].letterStyle.fontSize
                curLetters:pushBack(letters[j])
            end
        end
    end

    Common.STICKER.richText.letters = curLetters
    Common.STICKER.richText:forceTypeSetting()
end

function CPage:setLineBeforeReadAnim(_func, _isEarlier)
    if #self.lines > 0 then
        for i = 1, #self.lines do
            self.lines[i]:setBeforeReadAnim(_func, _isEarlier)
        end
    end
end

function CPage:setLineReadingAnim(_func, _isEarlier)
    if #self.lines > 0 then
        for i = 1, #self.lines do
            self.lines[i]:setReadingAnim(_func, _isEarlier)
        end
    end
end

function CPage:setLineAfterReadAnim(_func, _isEarlier)
    if #self.lines > 0 then
        for i = 1, #self.lines do
            self.lines[i]:setAfterReadAnim(_func, _isEarlier)
        end
    end
end

function CPage:setWordBeforeReadAnim(_func, _isEarlier)
    if #self.words > 0 then
        for i = 1, #self.words do
            self.words[i]:setBeforeReadAnim(_func, _isEarlier)
        end
    end
end

function CPage:setWordReadingAnim(_func, _isEarlier)
    if #self.words > 0 then
        for i = 1, #self.words do
            self.words[i]:setReadingAnim(_func, _isEarlier)
        end
    end
end

function CPage:setWordAfterReadAnim(_func, _isEarlier)
    if #self.words > 0 then
        for i = 1, #self.words do
            self.words[i]:setAfterReadAnim(_func, _isEarlier)
        end
    end
end

function CPage:setReadingAnim(_func)
    self.readingAnim = _func
end

function CPage:setAfterReadAnim(_func)
    self.afterReadAnim = _func
end

function CPage:animing(_time, keywordEnabled)
    if self.enable == false then
        Common.flushCmd(Common.STICKER)
        Common.STICKER.richText.str = ""
        Common.STICKER.richText:forceTypeSetting()
        return
    end
    local t = _time

    if Common.STICKER.richText.str ~= self:getStr() then

    end

    self:_syncStr()
    self:_syncLetters()

    local p = (t - self.startTime) / (self.endTime - self.startTime)
    if self.readingAnim then
        self:readingAnim(p, self:getLetters(), _time)
    end

    -- line animations
    if #self.lines > 0 then
        for i = 1, #self.lines do
            self.lines[i]:animingEarlier(t)
        end

        if keywordEnabled then
            for i = 1, #self.lines do
                local words = self.lines[i]:getWords()
                for j = 1, #words do
                    words[j]:brushWord()
                end
            end
        end
        self:updateSpaceWhenDecorationFollowingLetter(true)

        Common.STICKER.richText:forceTypeSetting()


        for i = 1, #self.lines do
            self.lines[i]:animing(t)
        end
        self:updateSpaceWhenDecorationFollowingLetter()
    end

    -- word animations
    local handleReadingWord = false
    if self.words and #self.words > 0 then
        local readingWord = nil

        if Common.earlierbrushWord and keywordEnabled then
            for i = 1, #self.words do
                if self.words[i]:hasWholeAnimDelegate() then
                    self.words[i]:brushWord()
                end
            end
        end

        for i = 1, #self.words do
            local state = self.words[i]:getState(t)
            if state == Common.WORD_STATE.BEFORE_READ or state == Common.WORD_STATE.AFTER_READ then
                if self.words[i]:hasWholeAnimDelegate() then
                    self.words[i]:animing(t)
                end
            elseif state == Common.WORD_STATE.READING then
                if self.words[i]:hasWholeAnimDelegate() then
                    readingWord = self.words[i]
                end
            end
        end

        if Common.earlierbrushWord == false and keywordEnabled then
            for i = 1, #self.words do
                if self.words[i]:hasWholeAnimDelegate() then
                    self.words[i]:brushWord()
                end
            end
        end

        if readingWord then
            if readingWord:hasWholeAnimDelegate() then
                handleReadingWord = true
                readingWord:animingEarlier(t)
                self:updateSpaceWhenDecorationFollowingLetter(true)

                self:applyKeywordSupersize()

                Common.STICKER.richText:forceTypeSetting()
                
                readingWord:animing(t)
                self:updateSpaceWhenDecorationFollowingLetter()
            end
        end
    end

    if handleReadingWord == false then
        self:applyKeywordSupersize()
    end
    
    if self.afterReadAnim then
        self:updateSpaceWhenDecorationFollowingLetter(true)
        
        Common.STICKER.richText:forceTypeSetting()
        self:afterReadAnim(p, self:getLetters(), _time)
        self:updateSpaceWhenDecorationFollowingLetter()
    end

end

function CPage:applyKeywordSupersize()
    local keyword_supersize = Common.superSize
    local range = {}
    local curRange = 0

    if #self.lines > 0 then
        for lineIndex = 1, #self.lines do
            local words = self.lines[lineIndex].words
            for i = 1, #words do
                local word = words[i]
                local count = Common.getLetterCount(word.str)
                if word.isKey then
                    table.insert(range, curRange + lineIndex - 1)
                    table.insert(range, curRange + lineIndex - 1 + count)
                end
                curRange = curRange + count
            end
        end
    else
        for i = 1, #self.words do
            local word = self.words[i]
            local count = Common.getLetterCount(word.str)
            if word.isKey then
                table.insert(range, curRange)
                table.insert(range, curRange + count)
            end
            curRange = curRange + count
        end
    end
    if #range == 0 then return end

    local letters = Common.STICKER.richText.letters
    local data = {values={}}
    for i = 1, #range, 2 do
        table.insert(data.values, {
            name= "s",
            value= keyword_supersize,
            start= range[i],
            ["end"]= range[i+1],
            overlayMode= "mul",
            selectorUnit= "word"  -- this field is useless in this case but required
        })
    end
    if Amaz.SwingTemplateUtils then
        local swingTemplateUtils = Amaz.SwingTemplateUtils()
        if swingTemplateUtils.captionSetParamsBatch == nil then
            return
        end
        swingTemplateUtils:captionSetParamsBatch(Common.STICKER.richText, json.encode(data))
    end

end

function CPage:updateSpaceWhenDecorationFollowingLetter(_is_earlier)
    -- check " "(space) visible if decorationFollowingLetter is true
    -- the next letter has more power to affect current space letter
    -- the last letter is the second power
    if Common.STICKER.richText.isDecorationFollowingLetter == false then
        return
    end

    local function followLetter(cur_letter, target_letter)
        if _is_earlier == true then
            cur_letter.letterStyle = target_letter.letterStyle:clone()
        else
            cur_letter.position = target_letter.position - target_letter.initialPosition + cur_letter.initialPosition
            cur_letter.rotate = target_letter.rotate
            cur_letter.scale = target_letter.scale
        end
    end

    local letter_size = Common.STICKER.richText.letters:size()
    for i = 1, letter_size do
        local cur_letter = Common.STICKER.richText.letters:get(i-1)
        if cur_letter.utf8 == " " then
            local next_letter = nil
            if i < letter_size then
                next_letter = Common.STICKER.richText.letters:get(i)
                if _is_earlier == true then
                    cur_letter.instanceColor = next_letter.instanceColor
                end
                followLetter(cur_letter, next_letter)
            end

            local last_letter = nil
            if next_letter == nil then
                if i - 2 >= 1 then
                    last_letter = Common.STICKER.richText.letters:get(i-2)
                    if _is_earlier then
                        cur_letter.instanceColor = last_letter.instanceColor
                    end
                    followLetter(cur_letter, last_letter)
                end
            end

            if last_letter == nil and next_letter == nil  then
                if _is_earlier then
                    cur_letter.instanceColor = Amaz.Color(1,1,1,0)
                end
            end
        end
    end
end

function CPage:getReadingWord(_time)
    local t = _time
    local word = nil
    if self.words and #self.words > 0 then
        for i = 1, #self.words do
            local w = self.words[i]
            if w:getState(t) == Common.WORD_STATE.READING then
                word = w
                break
            end
        end
    end
    return word
end

function CPage:getReadingLine(_time)
    local t = _time
    local line = nil
    if self.lines and #self.lines > 0 then
        for i = 1, #self.lines do
            local l = self.lines[i]
            if l:getState(t) == Common.LINE_STATE.READING then
                line = l
                break
            end
        end
    end
    return line
end

function CPage:getInitialCenter()
    return self:getCenter(function(_l)
        return _l.initialPosition
    end)
end

function CPage:getCenter(_centerDelegate)
    if self:isLegal() == false then
        return Amaz.Vector2f(-1, -1)
    end

    local rect = self:getRect(_centerDelegate)
    local center = Amaz.Vector2f(rect.x + rect.width * 0.5, rect.y + rect.height * 0.5)
    return center
end

function CPage:isLegal()
    return #self.words > 0 or #self.lines > 0
end

function CPage:destroy()
    self.words = {}
    self.str = ""
    self.letters = {}
    self.idx = -1
end

--[[  ****************************************
        CaptionModule: manager all the CPage
    --    **************************************** ]]
local CaptionModule = {}
CaptionModule.__index = CaptionModule
CaptionModule.TEXT_STICKER = "TEXT_STICKER"

function CaptionModule.new(_sticker)
    local self = setmetatable({}, CaptionModule)

    self.sticker = _sticker
    Common.STICKER = self.sticker
    self.pages = {}
    self.words = {}
    self.textCapital = "none"
    return self
end

function CaptionModule:getLegalLetterCount()
    local count = 0
    for i = 1, #self.words do
        local sw = self.words[i]
        if sw:isLegal() then
            count = count + sw:getLetterCount()
        end
    end
    return count
end

function CaptionModule:getLetterCount()
    return Common.getLetterCount(Common.STICKER.richText.str)
end

-- custom change captionInfo
function CaptionModule:setCaptionInfoCustom(_customDelegate)
    if self.captionInfo == nil then
        self:splitSimpleCaption()
    end

    self.captionInfo = _customDelegate(self.captionInfo)
end

function CaptionModule:getDuration()
    if self:isLegal() == false then
        return -1
    end
    local st, et = Common.getTimeRange(self.captionRawInfo.words)
    return et - st
end

function CaptionModule:isLegal()
    return not (self.captionRawInfo == nil)
end

function CaptionModule:registerMergeModule(_module)
    mergeModule = _module
end

function CaptionModule:init(captionInfo)
    if Common.isEditor then
        local rootDir = self.sticker.entity.scene.assetMgr.rootDir
        self.rawCaptionStr = Common.readStrFromFile(rootDir .. "test/caption_fake_data2.json")
        -- self.captionParamsStr = Common.readStrFromFile(rootDir .. "test/caption_params_zh_v2.json")
    end

    if self.rawCaptionStr then
        self.captionRawInfo = json.decode(self.rawCaptionStr)
        local str = ""
        for i=1, #self.captionRawInfo.words do
            str = str .. self.captionRawInfo.words[i].text
        end
        self.captionRawInfo.text = str
    end

    if self.captionParamsStr then
        self.captionParams = json.decode(self.captionParamsStr)
    else
        self.captionParams = {}
    end

    if captionInfo ~= nil then
        self.captionRawInfo = captionInfo
    end

    if mergeModule == nil and self.sticker.getModule then
        mergeModule = self.sticker:getModule("LetterStyleMergeModule")
    end
    if Common.isEditor then
        -- change text in editor
        Common.STICKER.richText.str = self.captionRawInfo.text
        Common.STICKER.richText:forceTypeSetting()
    end

    self.enable = self:isLegal()
    self.fitPageMaxLine = false
    self.extraLineSpacing = 1

    self.wordOverlapLeft = 0
    self.wordOverlapRight = 0
end

function CaptionModule:setRichText(_richText)
    if _richText == nil then
        return
    end
    -- self.sticker = _richText
    Common.STICKER = _richText
    -- self:init()
end

function CaptionModule:_getBaseLetters()
    local str = Common.STICKER.richText.str
    str = self:applyCapital(str)
    Common.STICKER.richText.str = str
    Common.STICKER.richText:forceTypeSetting()
    return Common.STICKER.richText.letters:clone()
end

function CaptionModule:_getMergedLetters(_baseLetters)
    if mergeModule then
        local relative = false
        if self.captionParams ~= nil and self.captionParams.keyword_supersize ~= nil then
            relative = true
        end
        mergeModule:setRelative(relative)
        local str = Common.STICKER.richText.str
        str = self:applyKeywordCapital(str)
        -- Common.STICKER.richText:setString(str, true)
        Common.STICKER.richText.str = str
        Common.STICKER.richText:forceTypeSetting()
        mergeModule:applyTextStyle(Common.STICKER)  -- letterStyle setting should be performed after str setting; otherwise, forceTypeSetting resets letterStyle
        return Common.STICKER.richText.letters:clone()
    end
    return _baseLetters:clone()
end

function CaptionModule:initCaptionInfo(_extendLeft, _extendRight, _timeSpace)
    --[[    captionInfo include
            [
                {
                    -- normal
                    idx = 1,
                    legal_idx = 1,
                    text = "new",
                    start_time = 0, ms
                    end_time = 10,  ms
                    ori_start_letter_idx = 1
                    pack_start_time = 0,
                    pack_end_time = 1,

                    -- page about
                    page_idx = 1

                    -- line about
                    line_idx = 1 or nil
                }
                ...
            ]
        ]]
    local extendRight = _extendRight == nil and 0.5 or Common.clamp(_extendRight, 0, 1)
    local extendLeft = _extendLeft == nil and 0.5 or Common.clamp(_extendLeft, 0, 1 - extendRight)
    local timeSpace = _timeSpace == nil and 1000 or _timeSpace

    local curLegalWordIdx = 1
    local curOriStartLetterIdx = 0
    local curkeywordIdx = 1

    local wordInfos = {}
    for i = 1, #self.captionRawInfo.words do
        local info = self.captionRawInfo.words[i]

        -- remove the illegal info if [first or last]
        local continue = false
        continue = (i == #self.captionRawInfo.words) and (Common.isLegalStr(info.text) == false)

        -- if first info.text == " " (stupid input)
        if (i == 1) and (Common.isLegalStr(info.text) == false) then
            continue = true
            curOriStartLetterIdx = curOriStartLetterIdx + Common.getLetterCount(info.text)
        end

        if not continue then
            info.idx = i
            info.pack_start_time = info.start_time
            info.pack_end_time = info.end_time

            if not Common.isLegalStr(info.text) then
                info.legal_idx = -1
                info.keyword_idx = -1
            else
                info.legal_idx = curLegalWordIdx
                curLegalWordIdx = curLegalWordIdx + 1
                if not info.is_key then
                    info.keyword_idx = -1
                else
                    info.keyword_idx = curkeywordIdx
                    curkeywordIdx = curkeywordIdx + 1
                end
            end
            info.ori_start_letter_idx = curOriStartLetterIdx
            table.insert(wordInfos, info)

            curOriStartLetterIdx = curOriStartLetterIdx + Common.getLetterCount(info.text)
        end
    end


    self.captionInfo = { words = {} }
    self.words = {}

    self.oriWordWrapWidth = Common.STICKER.richText.typeSettingParam.wordWrapWidth
    if Common.STICKER.richText.typeSettingParam.lineSpacingMode ~= nil then
        self.oriLineSpacingMode = Common.STICKER.richText.typeSettingParam.lineSpacingMode
    end

    if self.fitPageMaxLine then
        -- self.oriWordWrapWidth = self.sticker.richText.typeSettingParam.wordWrapWidth
        Common.STICKER.richText.typeSettingParam.wordWrapWidth = 999999
        Common.STICKER.richText:forceTypeSetting()
    end

    local baseLetters = self:_getBaseLetters()
    local mergedLetters = self:_getMergedLetters(baseLetters)

    for i = 1, #wordInfos do
        local info = wordInfos[i]

        if info.legal_idx > 0 then
            local nextLegalFlag = true

            local idx = i + 1
            while nextLegalFlag and idx <= #wordInfos do
                local nextInfo = wordInfos[idx]
                nextLegalFlag = nextInfo.legal_idx < 0

                idx = idx + 1

                if nextLegalFlag then
                    nextInfo.pack_start_time = info.pack_end_time
                    nextInfo.pack_end_time = info.pack_end_time
                else
                    if nextInfo.start_time < info.end_time then
                        nextInfo.start_time = info.end_time
                    else
                        local duration = math.max(nextInfo.start_time - info.end_time, 0)
                        if duration > timeSpace then
                            local centerTime = (nextInfo.start_time + info.end_time) * 0.5
                            info.pack_end_time = info.end_time + (centerTime - info.end_time) * extendRight
                            nextInfo.pack_start_time = nextInfo.start_time - (centerTime - info.end_time) * extendLeft
                        else
                            info.pack_end_time = info.end_time + duration * extendRight
                            nextInfo.pack_start_time = nextInfo.start_time - duration * extendLeft
                        end
                    end
                end
            end
        end

        -- Amaz.LOGE("lrc caption init info ["..i, tostring(cjson.encode(info)))
        table.insert(self.captionInfo.words, info)

        local word = CWord.new(info)
        local letters = {}
        local mgdLetters = {}
        local oriStartLetterIdx = info.ori_start_letter_idx
        local lCount = Common.getLetterCount(word:getStr())
        for j = oriStartLetterIdx, oriStartLetterIdx + lCount - 1 do
            if j >= baseLetters:size() or j >= mergedLetters:size() then
                break
            end
            local letter = baseLetters:get(j)
            table.insert(letters, letter)

            local mgdLetter = mergedLetters:get(j)
            table.insert(mgdLetters, mgdLetter)
        end

        word:setLetters(letters)
        word:setOriLetters(mgdLetters)
        table.insert(self.words, word)
    end

    -- set the next word
    for i = 1, #self.words do
        local curWord = self.words[i]
        if curWord:isLegal() then
            local nextIdx = i
            local nextWord = nil
            while nextIdx <= #self.words and nextWord == nil do
                nextIdx = nextIdx + 1
                local next = self.words[nextIdx]
                if next and next:isLegal() then
                    nextWord = self.words[nextIdx]
                end
            end
            curWord:setNextWord(nextWord)


            local lastIdx = i
            local lastWord = nil
            while lastIdx > 1 and lastWord == nil do
                lastIdx = lastIdx - 1
                local last = self.words[lastIdx]
                if last and last:isLegal() then
                    lastWord = self.words[lastIdx]
                end
            end
            curWord:setLastWord(lastWord)
        end
    end
end

function CaptionModule:setWordOverlap(_left, _right)
    if _left < 0 then
        self.wordOverlapLeft = 0
    else
        self.wordOverlapLeft = math.min(_left, 1)
    end

    if _right < 0 then
        self.wordOverlapRight = 0
    else
        self.wordOverlapRight = math.min(_right, 1)
    end
end

function CaptionModule:_updateWordsOverlap(_overlapLeft, _overlapRight)
    for i = 1, #self.words do
        local word = self.words[i]

        local lastWord = word:getLastWord()
        local nextWord = word:getNextWord()

        if lastWord then
            word.startTime = word.packStartTime - (word.packStartTime - lastWord.packStartTime) * _overlapLeft
            word.startTime = math.max(word.startTime, lastWord.packStartTime)
        end

        if nextWord then
            word.endTime = word.packEndTime + (nextWord.packEndTime - word.packEndTime) * _overlapRight
            word.endTime = math.min(word.endTime, nextWord.endTime)
        end
    end
end

function CaptionModule:setMergeMode(_mode)
    Common.mergeBlendMode = _mode
end

function CaptionModule:_getSupersize()
    if self.captionParams == nil or self.captionParams.keyword_supersize == nil then
        return 1
    end
    local supersize = self.captionParams.keyword_supersize
    if ("line" == self.captionParams.keyword_isolation or "page" == self.captionParams.keyword_isolation) and self.captionParams.keyword_isolation_supersize ~= nil and self.captionParams.keyword_isolation_supersize > 0 then
        supersize = supersize * self.captionParams.keyword_isolation_supersize
    end
    return supersize
end

function CaptionModule:applyCapital(str)
    if Amaz.SwingTemplateUtils == nil then return str end
    if not self.captionRawInfo or #str == 0 then
        return str
    end
    if not (self.textCapital == "upper" or self.textCapital == "lower" or self.textCapital == "mixed" or self.textCapital == "none") then
        return str
    end
    if self.textCapital == "none" then
        return str
    end

    local dic = {
        ["upper"] = 0,
        ["lower"] = 1,
        ["mixed"] = 2
    }

    local swingTemplateUtils = Amaz.SwingTemplateUtils()
    if swingTemplateUtils.convertTextCase == nil then
        return str
    end
    local out = swingTemplateUtils:convertTextCase(str, dic[self.textCapital])
    if #out ~= #str then
        Amaz.LOGE("applyCapital", "case of no text is converted!")
        return str
    end
    local p = 1
    for i = 1, #self.captionRawInfo.words do
        local word = self.captionRawInfo.words[i]
        word.text = out:sub(p, p + #word.text -1)
        p = p + #word.text
    end
    return out
end

function CaptionModule:applyKeywordCapital(str)
    if Amaz.SwingTemplateUtils == nil then return str end
    if not self.captionRawInfo or not self.captionParams or not self.captionParams.keyword_capital then
        return str
    end
    local keyword_capital = self.captionParams.keyword_capital
    if not (keyword_capital == "upper" or keyword_capital == "lower" or keyword_capital == "mixed" or keyword_capital == "none") then
        return str
    end
    if keyword_capital == "none" then
        return str
    end

    local s = ""
    for i = 1, #self.captionRawInfo.words do
        if self.captionRawInfo.words[i].is_key then
            s = s.. self.captionRawInfo.words[i].text.. " "
        end
    end
    if #s == 0 then
        return str
    end
    local dic = {
        ["upper"] = 0,
        ["lower"] = 1,
        ["mixed"] = 2
    }

    local swingTemplateUtils = Amaz.SwingTemplateUtils()
    if swingTemplateUtils.convertTextCase == nil then
        return str
    end
    local out = swingTemplateUtils:convertTextCase(s, dic[keyword_capital])
    if #out ~= #s then
        Amaz.LOGE("applyKeywordCapital", "case of no text is converted!")
        return str
    end
    local p = 1
    local q = 1
    local text = ""
    for i = 1, #self.captionRawInfo.words do
        local word = self.captionRawInfo.words[i]
        if word.is_key then
            word.text = out:sub(p, p + #word.text -1)
            p = p + #word.text + 1
            text = text.. word.text
        else
            text = text.. str:sub(q, q + #word.text -1)
        end
        q = q + #word.text
    end
    if #text > #str then
        text = text:sub(1, #str)
    elseif #text < #str then
        text = text .. str:sub(q, #str)
    end
    return text
end

function CaptionModule:splitPage(_left, _right, _timeSpace)
    self:initCaptionInfo(_left, _right, _timeSpace)

    self:_updateWordsOverlap(self.wordOverlapLeft, self.wordOverlapRight)

    self.pages = {}
    local pageIdx = 1
    local page = CPage.new(pageIdx)
    
    local function _replaceSpaces()
        for i = 1, #self.pages do
            local page = self.pages[i]
            page:_replaceSpaces()
        end
    end

    local function getLinesByReturns()
        local lineList = {}
        local lineIdx = 1
        local lineObj = CLine.new(lineIdx, page)

        local function tryCreateLine()
            if lineObj:getLegalWordCount() > 0 then
                lineObj:refresh()
                table.insert(lineList, lineObj)
                lineIdx = lineIdx + 1
                lineObj = CLine.new(lineIdx, page)
            end
        end

        for i = 1, #self.words do
            local word = self.words[i]
            if word.str == '\n' then
                tryCreateLine()
            else
                lineObj:addWord(word)
                word:setLine(lineObj)
            end
        end
        tryCreateLine()

        return lineList
    end

    local function getForcedLines(lines)
        local lineList = {}
        local lineIdx = 1
        local lineObj = CLine.new(lineIdx, page)

        local function tryCreateLine(forcePage)
            if lineObj:getLegalWordCount() > 0 then
                lineObj:refresh()
                lineObj.forcePage = forcePage
                table.insert(lineList, lineObj)
                lineIdx = lineIdx + 1
                lineObj = CLine.new(lineIdx, page)
            end
        end

        local lastForceLine = nil
        local lastForcePage = nil
        for idx = 1, #lines do
            local line = lines[idx]
            for i = 1, #line.words do
                local word = line.words[i]

                local forceLine = self.captionParams.keyword_isolation == "line" and word.isKey == true
                local forcePage = self.captionParams.keyword_isolation == "page" and word.isKey == true
                local forceLineChanged = forceLine ~= lastForceLine and lastForceLine ~= nil and word:isLegal()
                local forcePageChanged = forcePage ~= lastForcePage and lastForcePage ~= nil and word:isLegal()
                if forceLineChanged or forcePageChanged then
                    tryCreateLine(lastForcePage)
                end

                lineObj:addWord(word)
                word:setLine(lineObj)
                if word:isLegal() then
                    lastForceLine = forceLine
                    lastForcePage = forcePage
                end
            end
            tryCreateLine(lastForcePage)
        end

        return lineList
    end

    local function getLinesLimitByWords(_wordCountList, _widthLimit, resetWordCount)
        local lines = getLinesByReturns()
        lines = getForcedLines(lines)
        if _widthLimit == nil then
            _widthLimit = true
        end
        local wordCountListIdx = 1
        local wordCountPerLineLimit = _wordCountList[wordCountListIdx]

        local lineList = {}
        local lineIdx = 1
        local lineObj = CLine.new(lineIdx, page)
        local curLineLegalWordCount = 0

        local function tryCreateLine(forcePage, needReset)
            if lineObj:getLegalWordCount() > 0 then
                lineObj:refresh()
                lineObj.forcePage = forcePage
                table.insert(lineList, lineObj)
                lineIdx = lineIdx + 1
                lineObj = CLine.new(lineIdx, page)
                if needReset then
                    wordCountListIdx = wordCountListIdx + 1
                    wordCountPerLineLimit = _wordCountList[(wordCountListIdx - 1) % #_wordCountList + 1]
                    curLineLegalWordCount = 0
                end
            end
        end

        for idx = 1, #lines do
            local line = lines[idx]
            for i = 1, #line.words do
                local word = line.words[i]

                local curLineWidth = lineObj:getRect().width
                local fitWrapWidthFlag = curLineWidth + word:getRect().width + 50 > self.oriWordWrapWidth
                if curLineLegalWordCount < 1 then
                    fitWrapWidthFlag = false
                end

                if curLineLegalWordCount >= wordCountPerLineLimit then
                    tryCreateLine(line.forcePage, true)
                elseif (fitWrapWidthFlag and _widthLimit) then
                    tryCreateLine(line.forcePage, resetWordCount)
                end

                lineObj:addWord(word)
                word:setLine(lineObj)
                if word:isLegal() then
                    curLineLegalWordCount = curLineLegalWordCount + 1
                end
            end
            tryCreateLine(line.forcePage, true)
        end

        return lineList
    end

    local function getLinesLimitByLetters(_letterCountList, _percent)
        local lines = getLinesByReturns()
        lines = getForcedLines(lines)
        if _percent == nil then
            _percent = 1
        end
        local letterCountListIdx = 1
        local letterCountPerLineLimit = _letterCountList[letterCountListIdx]

        local lineList = {}
        local lineIdx = 1
        local lineObj = CLine.new(lineIdx, page)
        local curLetterCount = 0

        local function tryCreateLine(forcePage)
            if lineObj:getLegalWordCount() > 0 then
                lineObj:refresh()
                lineObj.forcePage = forcePage
                table.insert(lineList, lineObj)
                lineIdx = lineIdx + 1
                lineObj = CLine.new(lineIdx, page)

                curLetterCount = 0

                letterCountListIdx = letterCountListIdx + 1
                letterCountPerLineLimit = _letterCountList[(letterCountListIdx - 1) % #_letterCountList + 1]
            end
        end

        local needAdd = true

        for idx = 1, #lines do
            local line = lines[idx]
            for i = 1, #line.words do
                local word = line.words[i]
                local wordLetterCount = word:getLetterCount()
                if word:isLegal() == false then
                    wordLetterCount = 0
                end

                -- first word must be inserted into the line even if its lengths exceeds the maximum; otherwise, letter count is not allowed to exceed the maximum
                if lineObj:getWordCount() < 1 and word:isLegal() then
                    lineObj:addWord(word)
                    word:setLine(lineObj)
                    curLetterCount = curLetterCount + wordLetterCount
                else
                    needAdd = true
                    if curLetterCount + wordLetterCount >= letterCountPerLineLimit then
                        -- patch: if letter count exceeds the maximum within _percent, it is allowed to be inserted into the line
                        if wordLetterCount * _percent <= (letterCountPerLineLimit - curLetterCount) then
                            if lineObj:getWordCount() > 0 or word:isLegal() then
                                lineObj:addWord(word)
                                word:setLine(lineObj)
                                curLetterCount = curLetterCount + wordLetterCount
                            end
                            needAdd = false
                        end
                        tryCreateLine(line.forcePage)
                    end

                    if (lineObj:getWordCount() > 0 or word:isLegal()) and needAdd == true then
                        lineObj:addWord(word)
                        word:setLine(lineObj)
                        curLetterCount = curLetterCount + wordLetterCount
                    end
                end
            end
            tryCreateLine(line.forcePage)
        end

        return lineList
    end

    local function getPagesLimitByLines(_lines, _lineCountList)
        local lineCountIdx = 1
        local lineCountPerPageLimit = _lineCountList[lineCountIdx]
        local pageList = {}
        local curLineCount = 0

        local function tryCreatePage()
            -- page:refresh()
            if page:isLegal() then
                table.insert(pageList, page)
                pageIdx = pageIdx + 1
                page = CPage.new(pageIdx)
                curLineCount = 0

                lineCountIdx = lineCountIdx + 1
                lineCountPerPageLimit = _lineCountList[(lineCountIdx - 1) % #_lineCountList + 1]
            end
        end

        local lastForcePage = nil
        for i = 1, #_lines do
            local line = _lines[i]
            local forcePageChanged = line.forcePage ~= lastForcePage and lastForcePage ~= nil
            if curLineCount >= lineCountPerPageLimit or forcePageChanged then
                tryCreatePage()
            end

            page:addLine(line)
            line:setPage(page)
            curLineCount = curLineCount + 1
            lastForcePage = line.forcePage
        end

        if page:isLegal() then
            -- page:refresh()
            table.insert(pageList, page)
        end
        return pageList
    end

    return {
        Default = function()
            for i = 1, #self.words do
                local w = self.words[i]
                w:setPage(page)
                page:addWord(w)
            end
            -- page:refresh()
            table.insert(self.pages, page)
        end,

        wordCountPerPageLimit = function(_wordCountPerPage)
            local wordCount = _wordCountPerPage == nil and 1 or _wordCountPerPage

            local curLegalWordCount = 0

            local function tryCreatePage()
                if page:isLegal() then
                    -- page:refresh()
                    table.insert(self.pages, page)
                    pageIdx = pageIdx + 1
                    page = CPage.new(pageIdx)
                    curLegalWordCount = 0
                end
            end

            local lastForcePage = nil
            for i = 1, #self.words do
                local word = self.words[i]

                local forcePage = self.captionParams.keyword_isolation == "page" and word.isKey == true
                local forcePageChanged = forcePage ~= lastForcePage and lastForcePage ~= nil and word:isLegal()

                if curLegalWordCount >= wordCount or forcePageChanged then
                    tryCreatePage()
                end

                if page:getWordCount() > 0 or word:isLegal() then
                    if word:isLegal() then
                        curLegalWordCount = curLegalWordCount + 1
                    end
                    page:addWord(word)
                    word:setPage(page)
                end
                if word:isLegal() then
                    lastForcePage = forcePage
                end
            end

            if page:isLegal() then
                -- page:refresh()
                table.insert(self.pages, page)
            end
        end,

        LetterCountPerPageLimit = function(_letterCountPerPage, _percent)
            -- include illegal letter
            local letterCountLimit = _letterCountPerPage == nil and 1 or _letterCountPerPage
            local percent = _percent == nil and 0 or _percent
            percent = Common.clamp(percent, 0, 1)

            local curLetterCount = 0

            local function tryCreatePage()
                if page:isLegal() then
                    -- page:refresh()
                    table.insert(self.pages, page)
                    pageIdx = pageIdx + 1
                    page = CPage.new(pageIdx)
                    newPageFlag = false
                end
            end

            local lastForcePage = nil
            local newPageFlag = false
            for i = 1, #self.words do
                local word = self.words[i]
                local forcePage = self.captionParams.keyword_isolation == "page" and word.isKey == true
                local forcePageChanged = forcePage ~= lastForcePage and lastForcePage ~= nil and word:isLegal()

                if page:getLegalLetterCount() > 0 then
                    if word:isLegal() == false then
                        local nextIdx = i + 1
                        local nextLegalWord = nil
                        while nextIdx <= #self.words and nextLegalWord == nil do
                            if self.words[nextIdx]:isLegal() then
                                nextLegalWord = self.words[nextIdx]
                            end
                            nextIdx = nextIdx + 1
                        end

                        local curPageLetterCount = page:getLetterCount()

                        if nextLegalWord then
                            if (letterCountLimit - curPageLetterCount) < nextLegalWord:getLetterCount() * percent then
                                newPageFlag = true
                            end
                        end
                    else
                        local curPageLetterCount = page:getLetterCount()
                        if (letterCountLimit - curPageLetterCount) < word:getLetterCount() * percent then
                            newPageFlag = true
                        end
                    end
                end

                if newPageFlag then
                    tryCreatePage()
                    curLetterCount = 0
                else
                    curLetterCount = curLetterCount + word:getLetterCount()
                end

                if curLetterCount > 0 or word:isLegal() then
                    if forcePageChanged then
                        tryCreatePage()
                    end
                    page:addWord(word)
                    word:setPage(page)
                end
                if word:isLegal() then
                    lastForcePage = forcePage
                end
            end

            if page:isLegal() then
                -- page:refresh()
                table.insert(self.pages, page)
            end
        end,

        LineCountLimit = function(_wordCountPerLine, _lineCountPerPage, _limitFlag)
            if _limitFlag == nil then
                _limitFlag = false
            end
            -- handle all the line
            local wordCountPerLineLimit = _wordCountPerLine == nil and 1 or _wordCountPerLine

            local lines = getLinesLimitByWords({ wordCountPerLineLimit }, _limitFlag, true)
            -- handle all the page
            local lineCountPerPageLimit = _lineCountPerPage == nil and 2 or _lineCountPerPage

            local pages = getPagesLimitByLines(lines, { lineCountPerPageLimit })
            for i = 1, #pages do
                table.insert(self.pages, pages[i])
            end
            _replaceSpaces()
        end,

        singleLineInPageByRowth = function(_limitFlag)
            if _limitFlag == nil then
                _limitFlag = false
            end
            local wordCountPerLine = {}
            local curRowth = -1
            for i = 1, #self.words do
                local word = self.words[i]
                if word:isLegal() then
                    local rowth = word:getOriLetters()[1].rowth + 1
                    for j = 1, #word:getOriLetters() do
                        if Common.isLegalStr(word:getOriLetters()[j].utf8) then
                            rowth = word:getOriLetters()[j].rowth + 1
                            break
                        end
                    end
                    if curRowth < 0 or curRowth ~= rowth then
                        curRowth = rowth
                        wordCountPerLine[#wordCountPerLine + 1] = 0
                    end
                    wordCountPerLine[#wordCountPerLine] = wordCountPerLine[#wordCountPerLine] + 1
                end
            end
            local lines = getLinesLimitByWords(wordCountPerLine, _limitFlag, false)
            local pages = getPagesLimitByLines(lines, { 1 })
            for i = 1, #pages do
                table.insert(self.pages, pages[i])
            end
            _replaceSpaces()
        end,

        letterCountPerLineLimitInPage = function(_letterCountPerLine, _lineCountPerPage, _percent)
            -- handle all the line
            local letterCountPerLineLimit = _letterCountPerLine

            local lines = getLinesLimitByLetters({ letterCountPerLineLimit }, _percent)

            -- handle all the page
            local lineCountPerPageLimit = _lineCountPerPage == nil and 2 or _lineCountPerPage

            local pages = getPagesLimitByLines(lines, { lineCountPerPageLimit })
            for i = 1, #pages do
                table.insert(self.pages, pages[i])
            end
            _replaceSpaces()
        end,


        customLetterLineCountLimit = function(_letterLineList2D, _percent)
            local letterCountList = {}
            local lineCountList = {}
            for i = 1, #_letterLineList2D do
                for j = 1, #_letterLineList2D[i] do
                    table.insert(letterCountList, _letterLineList2D[i][j])
                end
                table.insert(lineCountList, #_letterLineList2D[i])
            end

            local lines = getLinesLimitByLetters(letterCountList, _percent)
            local pages = getPagesLimitByLines(lines, lineCountList)
            for i = 1, #pages do
                table.insert(self.pages, pages[i])
            end
            _replaceSpaces()
        end,

        customWordLineCountLimit = function(_wordLineList2D, _limitFlag)
            if _limitFlag == nil then
                _limitFlag = false
            end
            local wordCountList = {}
            local lineCountList = {}
            for i = 1, #_wordLineList2D do
                for j = 1, #_wordLineList2D[i] do
                    table.insert(wordCountList, _wordLineList2D[i][j])
                end
                table.insert(lineCountList, #_wordLineList2D[i])
            end

            local lines = getLinesLimitByWords(wordCountList, _limitFlag, true)
            
            local pages = getPagesLimitByLines(lines, lineCountList)
            for i = 1, #pages do
                table.insert(self.pages, pages[i])
            end
            _replaceSpaces()
        end

    }
end

function CaptionModule:setEarlierBrushKeyWord(_state)
    Common.earlierbrushWord = _state
end

function CaptionModule:getReadingPage(_time)
    local t = _time

    local page = nil
    if self.pages and #self.pages > 0 then
        for i = 1, #self.pages do
            local p = self.pages[i]
            if p:isReading(t) and p:getEnable() then
                page = p
                break
            end
        end
    end

    return page
end

function CaptionModule:setFitMaxLine(_fitFlag)
    self.fitPageMaxLine = _fitFlag
end

function CaptionModule:setExtraLineSpacing(_lineSpace)
    self.oriLineSpacing = Common.STICKER.richText.typeSettingParam.lineSpacing
    self.extraLineSpacing = _lineSpace
end

function CaptionModule:isKeywordEnabled()
    if self.captionParams == nil then return false end  -- no effect, because self.captionParams was initialized to {}
    if self.captionParams.enable_keyword then
        return mergeModule:isKeywordEnabled()
    end
    return true  -- when caption anim is directly used, instead of being used in caption template
end

function CaptionModule:animing(_time)
    if self.enable == false then
        return
    end

    local keywordEnabled = self:isKeywordEnabled()
    local t = _time

    local page = self:getReadingPage(t)
    if page then
        Common.superSize = self:_getSupersize()
        page:animing(t, keywordEnabled)
        return page, page:getReadingWord(t), page:getReadingLine(t)
    end

    Common.flushCmd(Common.STICKER)
    Common.STICKER.richText.str = ""
end

function CaptionModule:onSetProperty(key, value)
    if key == "caption_duration_info" and value ~= "" then
        Amaz.LOGE("lrc caption_duration_info", value)
        self.rawCaptionStr = value
    elseif key == "caption_params" and value ~= "" then
        Amaz.LOGE("lrc caption_params", value)
        self.captionParamsStr = value
    elseif key == "text_capital" and value ~= "" then
        Amaz.LOGE("lrc text_capital", value)
        self.textCapital = value
    end
end

function CaptionModule:setEnable(_val)
    self.enable = _val
end

function CaptionModule:refresh()
    if self.fitPageMaxLine == true then
        if Common.STICKER.richText.typeSettingParam.lineSpacingMode ~= nil then
            Common.STICKER.richText.typeSettingParam.lineSpacingMode = Amaz.LineSpacingMode.CLOSEST
        end
        for i = 1, #self.pages do
            self.pages[i]:setFitMaxLine(self.fitPageMaxLine)
            self.pages[i]:setExtraLineSpacing(self.extraLineSpacing)
            self.pages[i]:setOriLineSpacing(self.oriLineSpacing)
        end
    end

    for i = 1, #self.pages do
        self.pages[i]:refresh()
    end
end

function CaptionModule:getPages()
    self:refresh()
    return self.pages
end

function CaptionModule:getPagesWithoutRefresh()
    return self.pages
end

function CaptionModule:getWords()
    return self.words
end

function CaptionModule:getLegalWords()
    self.legalWords = {}
    for i = 1, #self.words do
        local w = self.words[i]
        if w:isLegal() then
            table.insert(self.legalWords, w)
        end
    end
    return self.legalWords
end

function CaptionModule:getWordCount()
    return #self.words
end

function CaptionModule:getLegalWordCount()
    local count = 0
    for i = 1, #self.words do
        local w = self.words[i]
        if w:isLegal() then
            count = count + 1
        end
    end
    return count
end

function CaptionModule:getCaptionRawInfo()
    return self.captionRawInfo
end

function CaptionModule:getCaptionParams()
    return self.captionParams
end

function CaptionModule:seek(_time)
end

function CaptionModule:reset()
    self.captionRawInfo = {}
    self.captionParams = {}
    self.captionInfo = { words = {} }
    self.pages = {}
    self.words = {}
    mergeModule = nil
    -- self.sticker = nil
    Common.sdfText = nil

    if self.oriWordWrapWidth then
        Common.STICKER.richText.typeSettingParam.wordWrapWidth = self.oriWordWrapWidth
    end

    if self.oriLineSpacingMode ~= nil then
        Common.STICKER.richText.typeSettingParam.lineSpacingMode = self.oriLineSpacingMode
    end

    if self.oriLineSpacing then
        Common.STICKER.richText.typeSettingParam.lineSpacing = self.oriLineSpacing
    end
end

return CaptionModule
