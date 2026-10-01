--[[  ****************************************
    TextCommonAnimModule: manager all the CloneText
--    **************************************** ]]  
local TextCommonAnimModule = {}
TextCommonAnimModule.__index = TextCommonAnimModule
TextCommonAnimModule.TEXT_STICKER = "TEXT_STICKER"

local function remap01(a,b,x)
    if x < a then return 0 end
    if x > b then return 1 end
    return (x-a)/(b-a)
end

local function mix(a,b,x)
    return a * (1-x) + b * x
end

function TextCommonAnimModule.new(_sticker)
    local self = setmetatable({}, TextCommonAnimModule)

    self.sticker = _sticker
    return self
end



function TextCommonAnimModule:splitLadderIn01(_iList, _firstStartP, _lastStartP, _duration)
    local count = #_iList
    local pRange = {}
    for i = 1, count do
        local curStartP = _firstStartP
        if count > 1 then
            curStartP = mix(_firstStartP, _lastStartP, (i-1)/(count-1))
        end
        local curEndP = curStartP + _duration
        
        pRange[i] = {curStartP, curEndP}
    end
    return function (_i, _p)
        local range = pRange[_i]
        return remap01(range[1], range[2], _p)
    end
end

-- todo: set bezier between first and last
function TextCommonAnimModule:setAnim(
    _letterList, _firstLetterStartP, 
    _lastLetterStartP, _animDuration, 
    _progress, _animFunc)

    local pRangeFunc = self:splitLadderIn01(_letterList, _firstLetterStartP, _lastLetterStartP, _animDuration)

    for i = 1, #_letterList do
        local curP = pRangeFunc(i, _progress)
        -- local l = _letterList[i]
        _animFunc(curP, _letterList, i)
    end
end

function TextCommonAnimModule:init()

end

function TextCommonAnimModule:seek()

end

function TextCommonAnimModule:reset()
end

return TextCommonAnimModule