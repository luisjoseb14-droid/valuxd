local isEditor = (Amaz.Macros and Amaz.Macros.EditorSDK) and true or false
local TextSticker = TextSticker or {}
TextSticker.__index = TextSticker


function TextSticker:_moduleCall(callbackName, ...)
    if self.modules then
        for _, moduleObj in pairs(self.modules) do
            local cn = callbackName
            if moduleObj[cn] then
                moduleObj[cn](moduleObj, ...)
            end
        end
    end
end

function TextSticker:getModule(name)
    -- Amaz.LOGI("lrc getModule", name)
    if self.modules and self.modules[name] then
        return self.modules[name]
    end
    return nil
end

function TextSticker:_call(_name, ...)
    if self[_name] then
        self[_name](self, ...)
    end
end

--[[ ******************************
    CALL when load the sticker
     ******************************]]
function TextSticker:onStart(comp) 
    --[[
        attribute for sticker
    --]] 
    -- business attr
    self.duration = 0
    self.curTime = 0

    -- Editor about ---
    -- self.autoPlay = false
    self.duration = 4

    -- Runtime ---
    -- self.progress = 0
    self.frame = 0
    
    --[[
        normal engine attribute 
    --]] 
    self.comp = comp
    self.entity = self.comp.entity
	self.text = self.comp.entity:getComponent("SDFText")
    if self.text == nil then
        local text = self.comp.entity:getComponent('Text')
        if text ~= nil then
			self.text = self.comp.entity:addComponent('SDFText')
            self.text:setTextWrapper(text)
        end
    end
	self.richText = self.comp.entity:getComponent("Text")
    self.trans = self.comp.entity:getComponent("Transform")
    self.renderer = self.comp.entity:getComponent("MeshRenderer")
    self.parentTrans = self.trans.parent
	if self.text ~= nil then
		self.renderer = self.comp.entity:getComponent("MeshRenderer")
	else
		self.renderer = self.comp.entity:getComponent("Sprite2DRenderer")
	end

    --[[
        register part
    --]] 
    if self.registerModules then
        self.modules = {}
        self:stickerRegistingModules(self.registerModules)
    end

    self:_call("textStart", comp)

    if isEditor then
        self:onEnter()
    end
end

function TextSticker:onUpdate(comp, time)
    if isEditor then
        if self.autoPlay then
            self.curTime = self.curTime + time
            self.progress = self.curTime % self.duration / self.duration
        else
            self.curTime = 0
        end
        self:seek(self.curTime)
    end
end

function TextSticker:stickerRegistingModules(moduleNameList)
    if self["_registerModule"] and moduleNameList then
        for i = 1, #moduleNameList do
            local mn = moduleNameList[i]
            self.modules[mn] = self:_registerModule("modules/"..mn)
        end
    end
end

function TextSticker:registingModule(_moduleName, _modulePath)
    self.modules[_moduleName] = self:_registerModule("modules/".._modulePath)
end

function TextSticker:getOriLetters()
    if self.oriLettersClone == nil and self.oriLetters then
        self.oriLettersClone = self.oriLetters:clone()
    end
    return self.oriLettersClone
end

function TextSticker:onSetProperty(key, value)
    self:_moduleCall("onSetProperty", key, value)
end

function TextSticker:seek(time)
    if isEditor then
    else
        self.progress = time % (self.duration+0.000001) / self.duration
    end

    self:_call("textSeek", time)
    self:_moduleCall("seek", time)
end

function TextSticker:beforeTextSystemUpdate(comp)
    self:_call("textBeforeUpdate", comp)
    self:_moduleCall("beforeUpdate", comp)
end

function TextSticker:afterTextSystemUpdate(comp)
    self:_call("textAfterUpdate", comp)
    self:_moduleCall("afterUpdate", comp)
end

--[[ ******************************
    reset the text data
     ******************************]]
function TextSticker:_reset()
    if self.richText and self.oriLetters then
        self.richText.letters = self.oriLetters
        -- self.richText.canvas = self.oriCanvas
    end
	if self.text then
        self.text.renderToRT = false
        self.text.targetRTExtraSize = Amaz.Vector2f(0.0, 0.0)
	end
    if self.trans and self.oriTextLocalPosition then
        self.trans.localScale = Amaz.Vector3f(1, 1, 1)
        self.trans.localPosition = self.oriTextLocalPosition
        self.trans.localEulerAngle = Amaz.Vector3f(0, 0, 0)
    end
    self:_call("textReset")
    self:_moduleCall("reset")
end

function TextSticker:setDuration(duration)
    self.duration = duration
end

--[[ ******************************
    only CALL when change the style and trans
     ****************************** ]]
function TextSticker:clear()
    self:_reset()
end

--[[ ******************************
    CALL when enter the anim or after clear function
     ******************************]]
function TextSticker:onEnter()
    self:_moduleCall("init")
    self.oriStr = self.richText.str
    if self.richText then
        self.oriLetters = self.richText.letters:clone()
        self.oriLettersClone = nil
    end
    if self.trans then
        self.oriTextLocalPosition = self.trans.localPosition
    end


    self:_call("textInit")
end

--[[ ******************************
    only CALL when leave the text anim
     ****************************** ]]
function TextSticker:onLeave()
    self:_reset()
end

return TextSticker
