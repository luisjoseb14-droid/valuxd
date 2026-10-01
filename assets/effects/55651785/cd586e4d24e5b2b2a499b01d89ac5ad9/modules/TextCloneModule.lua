local isEditor = (Amaz.Macros and Amaz.Macros.EditorSDK) and true or false
--[[  ****************************************
    storge the CloneText info
--    **************************************** ]]  
local CloneText = {}
CloneText.__index = CloneText

function CloneText.new(_sticker, _name, _mat)
    local self = setmetatable({}, CloneText)
    self.parentTrans = _sticker.trans
    local parentEntity = _sticker.entity
    self.entity = parentEntity.scene:createEntity("cloneText_".._name)

    self.entity.layer = _sticker.entity.layer
    self.trans = self.entity:cloneComponentOf(self.parentTrans)
    if _sticker.richText then
        self.richText = self.entity:cloneComponentOf(_sticker.richText)
    end
    self.renderer = self.entity:cloneComponentOf(_sticker.renderer)
    self:setMaterial(_mat)
    self.renderer.sortingOrder = _sticker.renderer.sortingOrder
    self.richText.richStr = _sticker.richText.richStr
    self.richText.letters = self.richText.letters   -- effect's trick: 
    self.richText:forceTypeSetting()
    self.trans.parent = _sticker.trans
    _sticker.trans.children:pushBack(self.trans)
    if _sticker.text then
        self.text = self.entity:cloneComponentOf(_sticker.text)
        if self.richText then
            self.text:setTextWrapper(self.richText)
            self.richText:forceTypeSetting()
        end
        if _sticker.text.effectTextParam == nil then
            return self
        end
    end

    ---- clone effectLayers (flower text)-----
    local effectLayers = _sticker.text.effectTextParam.effectLayers
	local cloneEffectTextParam = _sticker.text.effectTextParam

	if cloneEffectTextParam ~= nil and effectLayers ~= nil then
		local cloneEffectLayers = cloneEffectTextParam.effectLayers
		for i = 0, cloneEffectLayers:size() - 1 do 
			if i < effectLayers:size() then
				cloneEffectLayers:get(i).mat = effectLayers:get(i).mat
				cloneEffectLayers:get(i).texture = effectLayers:get(i).texture
			end
		end
	end
    return self
end

function CloneText:setMaterial(_mat)
    if _mat == nil then
        self.richText.canvas.renderToRT = false
        return
    end
    self.richText.canvas.renderToRT = true
    self.renderer.material = _mat:instantiate()
    self.material = self.renderer.material
end

function CloneText:getMaterial()
    return self.material
end

function CloneText:destroy()
    self.entity.scene:removeEntity(self.entity)
    self.parentTrans.children:erase(self.entity)
    self.entity = nil
    self = {}
end




--[[  ****************************************
    TextCloneModule: manager all the CloneText
--    **************************************** ]]  
local TextCloneModule = {}
TextCloneModule.__index = TextCloneModule
TextCloneModule.TEXT_STICKER = "TEXT_STICKER"

-- hide letter like flower letter
local function hideLetter(_letter)
    _letter.scale = Amaz.Vector2f(0,0)
    -- local closeFlowerLetter = function (_styles)
    --     for i = 0, _styles:size() - 1 do
    --         local s = _styles:get(i)
    --         if s.enable == true then
    --             s.enable = false
    --         end
    --     end
    -- end
    -- if isEditor then
    --     _letter.instanceColor = Amaz.Color(1, 1, 1, 1)
    --     return
    -- end

    -- local ls = _letter.letterStyle
    -- local rgba = ls.letterColorRGBA:copy()

    -- ls.letterColorRGBA = Amaz.Color(rgba.r, rgba.g, rgba.b, rgba.a*0)

    -- closeFlowerLetter(ls.strokes)
    -- closeFlowerLetter(ls.shadows)
    -- closeFlowerLetter(ls.innerShadows)
    -- ls.fill.enable = false

end


function TextCloneModule.new(_sticker)
    local self = setmetatable({}, TextCloneModule)

    self.sticker = _sticker
    self.cloneTextList = {}
    return self
end

function TextCloneModule:addCloneText(_mat)
    local cloneText = CloneText.new(self.sticker, #self.cloneTextList, _mat)
    table.insert(self.cloneTextList, cloneText)
    return cloneText
end

function TextCloneModule:getCloneTextList()
    return self.cloneTextList
end

function TextCloneModule:splitLineWithClone(_mat, _max_line)

    local richText = self.sticker.richText
    local perLineLetters = {}
    for i = 1, richText.letters:size() do
        local l = richText.letters:get(i-1)
        local rowth = l.rowth + 1       -- start with 0
        if perLineLetters[rowth] == nil then
            perLineLetters[rowth] = Amaz.Vector()
        end
        perLineLetters[rowth]:pushBack(l)
    end

    local curCloneTextList = {}
    local w = Amaz.BuiltinObject:getOutputTextureWidth()
    local h = Amaz.BuiltinObject:getOutputTextureHeight()
    if #perLineLetters > 1 then
        for i = 2, #perLineLetters do
            local letters = perLineLetters[i]
            local curCloneText = self:addCloneText(_mat)
            curCloneText.richText.letters = letters:clone()
            curCloneText.richText:forceTypeSetting()

            local oriFirstLetter = letters:get(0)
            local cloneFirstLetter = curCloneText.richText.letters:get(0)

            curCloneText.trans.localPosition = Amaz.Vector3f(
                (oriFirstLetter.position.x - cloneFirstLetter.position.x)/h*2,
                (oriFirstLetter.position.y - cloneFirstLetter.position.y)/h*2,
                0
            )

            -- hide ori letter
            for j = 1, letters:size() do
                hideLetter(letters:get(j-1))
            end

            table.insert(curCloneTextList, curCloneText)
        end

        return curCloneTextList
    end

    return nil
end

function TextCloneModule:splitWithCloneByRules(_rulesDelegate)
    
end

function TextCloneModule:init()

end

function TextCloneModule:seek()

end

function TextCloneModule:reset()
    for i = 1, #self.cloneTextList do
        local ct = self.cloneTextList[i]
        ct:destroy()
    end
    self.cloneTextList = {}
	collectgarbage("collect")
end

return TextCloneModule