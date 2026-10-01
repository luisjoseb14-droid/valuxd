
--[[  ****************************************
    CommonLetterModule: manager all the CloneText
--    **************************************** ]]  
local CommonLetterModule = {}
CommonLetterModule.__index = CommonLetterModule
CommonLetterModule.TEXT_STICKER = "TEXT_STICKER"

function CommonLetterModule.new(_sticker)
    local self = setmetatable({}, CommonLetterModule)

    self.sticker = _sticker
    return self
end


-- hide letter like flower letter
function CommonLetterModule:hideLetter(_letter)
    local closeFlowerLetter = function (_styles)
        for i = 0, _styles:size() - 1 do
            local s = _styles:get(i)
            if s.enable == true then
                s.enable = false
            end
        end
    end

    local ls = _letter.letterStyle
    local rgba = ls.letterColorRGBA:copy()
    ls.letterColorRGBA = Amaz.Color(rgba.r, rgba.g, rgba.b, rgba.a*0)

    closeFlowerLetter(ls.strokes)
    closeFlowerLetter(ls.shadows)
    closeFlowerLetter(ls.innerShadows)
    ls.fill.enable = false

end

function CommonLetterModule:getLettersRect(_letters)
    local leftDownPoint = nil
    local rightUpPoint = nil
    for i = 1, #_letters do
        local l = _letters[i]
        local rect = l.rect
        local initPos = l.initialPosition

        local curLeftDownPoint = {initPos.x-rect.width*0.5, initPos.y-rect.height*0.5}
        local curRightUpPoint = {initPos.x+rect.width*0.5, initPos.y+rect.height*0.5}
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
    return Amaz.Rect(leftDownPoint[1], leftDownPoint[2], 
                    rightUpPoint[1]-leftDownPoint[1], rightUpPoint[2]-leftDownPoint[2])
end

function CommonLetterModule:getLettersCenter(_letters)
    local pos = {0, 0}
    for i = 1, #_letters do
        local l = _letters[i]
        local initPos = l.initialPosition
        pos[1] = pos[1] + initPos.x
        pos[2] = pos[2] + initPos.y
    end
    return Amaz.Vector2f(pos[1]/#_letters, pos[2]/#_letters)
end

function CommonLetterModule:init()

end

function CommonLetterModule:seek()

end

function CommonLetterModule:reset()

end

return CommonLetterModule