local isEditor = (Amaz.Macros and Amaz.Macros.EditorSDK) and true or false
local exports = exports or {}
local LumiManagerLite = LumiManagerLite or {}
LumiManagerLite.__index = LumiManagerLite
---@class LumiManagerLite : ScriptComponent
---@field lumiEffectRoot Transform
---@field start_render_layer int
---@field start_render_order int
---@field InputTex Texture
---@field OutputTex Texture
---@field PingPongTex Texture

local AE_EFFECT_TAG = 'AE_EFFECT_TAG LumiTag'

function LumiManagerLite.new(construct, ...)
    local self = setmetatable({}, LumiManagerLite)

    self.lumiEffectRoot = nil
    self.start_render_layer = 1
    self.start_render_order = 1

    self.InputTex = nil
    self.OutputTex = nil
    self.PingPongTex = nil

    self.startTime = 0.0
    self.endTime = 6.0
    self.curTime = 0.0

    return self
end

function LumiManagerLite:onStart(comp)
    self.lumi_obj_extension = includeRelativePath("LumiObjectExtension")
    self.lumi_obj = nil
end

function LumiManagerLite:onDestroy(comp)
    if self.lumiEffectRoot and self.lumi_obj_extension then
        self.lumi_obj_extension.deregister(self.lumiEffectRoot.entity)
    end
    self.lumi_obj = nil
end

---@function [UI(Button="ReRender")]
function LumiManagerLite:getCameraCount()
    if self.lumiEffectRoot == nil then
        Amaz.LOGE(AE_EFFECT_TAG, 'Lumi Effect Root is nil, please check')
        return 0
    end

    self.lumi_obj = nil
    self:ReRender()

    local cam_count = 0
    if self.lumi_obj then
        cam_count = self.lumi_obj:getCameraCount()
        Amaz.LOGI(AE_EFFECT_TAG, self.lumi_obj.entity.name .. " camera_count: " .. tostring(cam_count))
    end
    return cam_count
end

function LumiManagerLite:ReRender()
    if self.lumiEffectRoot == nil then
        Amaz.LOGE(AE_EFFECT_TAG, 'Lumi Effect Root is nil, please check')
        return
    end

    -- re register
    self.lumi_obj = nil
    self:registerLumiObj(self.lumiEffectRoot, 1)

    if self.lumi_obj == nil then
        Amaz.LOGE(AE_EFFECT_TAG, 'No lumi_obj register')
        return
    end

    -- change layer & order
    self:updateCameraLayerAndOrder()

    -- change rt pingpong
    self:updateRtPingpong()
end

function LumiManagerLite:registerLumiObj(_trans, _idx)
    if _trans == nil then return end

    local script_comp = _trans.entity:getComponent("ScriptComponent")
    if script_comp then
        local lua_obj = Amaz.ScriptUtils.getLuaObj(script_comp:getScript())
        if lua_obj then
            self.lumi_obj_extension.deregister(_trans.entity)
            self.lumi_obj = self.lumi_obj_extension.register(_trans.entity)
        end
    end
end

function LumiManagerLite:updateCameraLayerAndOrder()
    if self.lumi_obj then
        self.lumi_obj:updateCameraLayerAndOrder(self.start_render_layer, self.start_render_order)
    end
end

function LumiManagerLite:updateRtPingpong()
    if self.lumi_obj then
        self.lumi_obj:updateRt(self.InputTex, self.OutputTex, self.PingPongTex)
    end
end

function LumiManagerLite:onUpdate(comp, deltaTime)
    if self.lumiEffectRoot == nil then
        Amaz.LOGE(AE_EFFECT_TAG, 'Lumi Effect Root is nil, please check')
        return
    end

    if self.lumi_obj == nil then
        self:registerLumiObj(self.lumiEffectRoot, 1)
    end

    self.curTime = self.curTime + deltaTime
    if self.lumi_obj then
        self.lumi_obj:setEffectAttr("startTime", self.startTime)
        self.lumi_obj:setEffectAttr("endTime", self.endTime)
        self.lumi_obj:setEffectAttr("curTime", self.curTime)
    end

    if self.lumi_obj and self.lumi_obj.updateMaterials then
        self.lumi_obj:updateMaterials(deltaTime)
    end
end

function LumiManagerLite:onEvent(comp, event)
    if self.lumiEffectRoot == nil then
        Amaz.LOGE(AE_EFFECT_TAG, 'Lumi Effect Root is nil, please check')
        return
    end

    if self.lumi_obj == nil then
        self:registerLumiObj(self.lumiEffectRoot, 1)
    end

    if self.lumi_obj == nil then
        Amaz.LOGE(AE_EFFECT_TAG, 'Failed to find lumi_obj')
        return
    end

    if event.type == Amaz.AppEventType.SetEffectIntensity then
        local key = event.args:get(0)
        local value = event.args:get(1)

        local TexNameSuffix = '_ae_plugin_tex_name'
        local suffixLen = string.len(TexNameSuffix)
        if string.sub(key, -suffixLen) == TexNameSuffix then
            key = string.sub(key, 1, -(suffixLen + 1))
            value = Amaz.BuiltinObject.getUserTexture(value)
            if string.len(key) <= 0 or value == nil then
                return
            end
        elseif type(value) == 'userdata' and value.size then
            local size = value:size()
            if size == 2 then
                value = Amaz.Vector2f(value:get(0), value:get(1))
            elseif size == 3 then
                value = Amaz.Vector3f(value:get(0), value:get(1), value:get(2))
            elseif size == 4 then
                value = Amaz.Color(value:get(0), value:get(1), value:get(2), value:get(3))
            end
        end

        -- Amaz.LOGI(AE_EFFECT_TAG, 'key: ' .. key .. ', value: ' .. tostring(value))
        self.lumi_obj:setEffectAttr(key, value)
    end
end

exports.LumiManagerLite = LumiManagerLite
return exports
