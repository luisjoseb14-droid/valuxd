
--[[  ****************************************
    storge the Sprite2D info
--    **************************************** ]]  
local Sprite2D = {}
Sprite2D.__index = Sprite2D

function Sprite2D.new(_sticker, _name, _mesh, _mat, _layer)
    local self = setmetatable({}, Sprite2D)
    self.entity = _sticker.entity.scene:createEntity("Sprite2D_".._name)
    self.trans = self.entity:cloneComponentOf(_sticker.trans)
    self.renderer = self.entity:cloneComponentOf(_sticker.renderer)
    if _sticker.trans then
        self.trans.parent = _sticker.trans
        self.parent = _sticker.trans
        _sticker.trans.children:pushBack(self.trans)
    end
    self:setMesh(_mesh)
    self:setMaterial(_mat)
    self.renderer.sortingOrder = _sticker.renderer.sortingOrder


    if _layer ~= nil then
        self.entity.layer = _layer
    end
    return self
end

function Sprite2D:setMesh(_mesh)
    if _mesh == nil then
        return 
    end
    self.renderer.mesh = _mesh
end

function Sprite2D:setMaterial(_mat)
    if _mat == nil then
        return
    end
    self.renderer.material = _mat:instantiate()
    self.material = self.renderer.material
end

function Sprite2D:getMaterial()
    return self.material
end

function Sprite2D:loadPicAndSetToMat(frame, picInfo, key)
    local curFrame = self.clamp(frame, picInfo.min, picInfo.max)
    local path = string.format(picInfo.path, curFrame)
    local pic = self.entity.scene.assetMgr:SyncLoad(path)
    self.material:setTex(key, pic)
end

function Sprite2D:destroy()
    if self.entity then
        self.entity.scene:removeEntity(self.entity)
        self.parent.children:erase(self.entity)
        self.entity = nil
    end
end

--[[  ****************************************
    Sprite2DModule: manage the sprite2D entity

        ***** quad like *****
        3 ---- 2
        | \    |
        |   \  |
        0 ---- 1

--    **************************************** ]]  
local Sprite2DModule = {}
Sprite2DModule.__index = Sprite2DModule
Sprite2DModule.TEXT_STICKER = "TEXT_STICKER"

--- new func of module
--- receives the 'self' variable of the original script as an argument
function Sprite2DModule.new(_sticker)
    local self = setmetatable({}, Sprite2DModule)
    self.sticker = _sticker
    self.sprite2DList = {}

    self.quadInfo = {}
    return self
end

function Sprite2DModule:addSprite2D(_mat, _layer)
    local quadInfo = self:_combineQuad()
    local quadMesh = self:generateMesh(quadInfo)
    local sprite2D = Sprite2D.new(self.sticker, #self.sprite2DList, quadMesh, _mat, _layer)
    table.insert(self.sprite2DList, sprite2D)
    return sprite2D
end

function Sprite2DModule:createMeshWithRect(rect, typeKind, screenParams, picRatio, RSTInfo, seedType, extendAttrs)
    local customMesh = Amaz.Mesh()
    local customSubMesh = Amaz.SubMesh()
    customSubMesh.primitive = Amaz.Primitive.TRIANGLES
    local pos = Amaz.VertexAttribDesc()
    pos.semantic = Amaz.VertexAttribType.POSITION
    local uv = Amaz.VertexAttribDesc()
    uv.semantic = Amaz.VertexAttribType.TEXCOORD0
    local vads = Amaz.Vector()
    vads:pushBack(pos)
    vads:pushBack(uv)
    local uviArray = {}
    for i = 1, math.max(extendAttrs, 7) do
        local uvi = Amaz.VertexAttribDesc()
        uvi.semantic = Amaz.VertexAttribType.TEXCOORD0 + i
        vads:pushBack(uvi)
        uviArray[i] = Amaz.Vec2Vector()
    end

    customMesh.vertexAttribs = vads
    local indexData = {}

    local count = 0

    local posArray = Amaz.Vec3Vector()
    local uvArray = Amaz.Vec2Vector()
    for i = 1, #rect do
        local rect_i = rect[i]
        local height = rect_i.height / screenParams.height
        local width = height * picRatio[i]
        if typeKind == 1 then
            width = rect_i.width / screenParams.height
            height = width / picRatio[i]
        end

        if picRatio[i] == -1 then
            width = rect_i.width / screenParams.height
            height = rect_i.height / screenParams.height
        end

        local rect_width = rect_i.width / screenParams.height
        local rect_height = rect_i.height / screenParams.height
        local center = {
            x = (rect_i.width * 0.5 + rect_i.x) / screenParams.height,
            y = (rect_i.height * 0.5 + rect_i.y) / screenParams.height
        }
        local seed = 0
        if seedType == 0 then
            seed = rect_i.rowth + 1
        elseif seedType == 1 then
            seed = i
        elseif seedType == 2 then
            seed = math.random()
        end
        for k = 0, 1 do
            for l = 0, 1 do
                local x = l * 2 - 1
                local y = k * 2 - 1
                x = x * width
                y = y * height
                local anchor = {
                    x = RSTInfo[i].anchor.x * width,
                    y = RSTInfo[i].anchor.y * height
                }
                x = x - anchor.x
                y = y - anchor.y
                x = x * RSTInfo[i].scale.x
                y = y * RSTInfo[i].scale.y
                x = x + anchor.x
                y = y + anchor.y
                x = x + RSTInfo[i].offset.x * rect_width
                y = y + RSTInfo[i].offset.y * rect_height
                x = x + center.x * 2.0
                y = y + center.y * 2.0
                local pos = Amaz.Vector3f(x, y, seed)
                posArray:pushBack(pos)
                local uv = Amaz.Vector2f(l, k)
                if typeKind == 0 then
                else
                    uv:set(1 - k, l)
                end
                uvArray:pushBack(uv)

                for j = 1, math.max(extendAttrs, 7) do
                    local uvi = Amaz.Vector2f(0, 0)
                    uviArray[j]:pushBack(uvi)
                end
            end
        end
        
        local p = count * 4
        table.insert(indexData, #indexData + 1, p)
        table.insert(indexData, #indexData + 1, p + 1)
        table.insert(indexData, #indexData + 1, p + 2)
        table.insert(indexData, #indexData + 1, p + 1)
        table.insert(indexData, #indexData + 1, p + 2 + 1)
        table.insert(indexData, #indexData + 1, p + 2)
        count = count + 1

    end
    local indices = Amaz.UInt16Vector()
    for i = 1, table.getn(indexData) do
        indices:pushBack(indexData[i])
    end

    customSubMesh.indices16 = indices
    customSubMesh.mesh = customMesh
    customMesh:addSubMesh(customSubMesh)

    customMesh:setVertexArray(posArray)
    customMesh:setUvArray(0, uvArray)
    for i = 1, math.max(extendAttrs, 7) do
        customMesh:setUvArray(i, uviArray[i])
    end
    customMesh.clearAfterUpload = true
    return customMesh
end

function Sprite2DModule:addQuadInfo(_s, _t, _extra_info)
    local info = {}
    info.pos = {
        Amaz.Vector3f(-_s.x+_t.x, -_s.y+_t.y, 0),
        Amaz.Vector3f( _s.x+_t.x, -_s.y+_t.y, 0),
        Amaz.Vector3f( _s.x+_t.x,  _s.y+_t.y, 0),
        Amaz.Vector3f(-_s.x+_t.x,  _s.y+_t.y, 0)
    }
    info.uv = {
        Amaz.Vector2f(0, 0),
        Amaz.Vector2f(1, 0),
        Amaz.Vector2f(1, 1),
        Amaz.Vector2f(0, 1),
    }
    info.indices = {0,1,3, 1,2,3}
    table.insert(self.quadInfo, info)
end

function Sprite2DModule:_combineQuad()
    local curQuad = {}
    curQuad.pos = {}
    curQuad.uv = {}
    curQuad.indices = {}
    for i = 1, #self.quadInfo do
        local info = self.quadInfo[i]

        for j = 1, #info.pos do
            local pos = info.pos[j]
            pos = Amaz.Vector3f(pos.x, pos.y, i)
            table.insert(curQuad.pos, pos)
        end

        for j = 1, #info.uv do
            table.insert(curQuad.uv, info.uv[j])
        end

        for j = 1, #info.indices do
            local indices = info.indices[j]
            indices = indices + (i-1) * 4
            table.insert(curQuad.indices, indices)
        end
    end
    self.quadInfo = {}
    return curQuad
end

function Sprite2DModule:generateMesh(meshInfo)
    local mesh = Amaz.Mesh()

    local posVAD = Amaz.VertexAttribDesc()
    posVAD.semantic = Amaz.VertexAttribType.POSITION
    local uvVAD = Amaz.VertexAttribDesc()
    uvVAD.semantic = Amaz.VertexAttribType.TEXCOORD0
    local vads = Amaz.Vector()
    vads:pushBack(posVAD)
    vads:pushBack(uvVAD)
    
    mesh.vertexAttribs = vads

    local posArray = Amaz.Vec3Vector()
    for i = 1, #meshInfo.pos do
        posArray:pushBack(meshInfo.pos[i])
    end
    local indices = Amaz.UInt16Vector()
    for i = 1, #meshInfo.indices do
        indices:pushBack(meshInfo.indices[i])
    end
    
    local uvArray = Amaz.Vec2Vector()
    for i = 1, #meshInfo.uv do
        uvArray:pushBack(meshInfo.uv[i])
    end



    mesh:setVertexArray(posArray)
    mesh:setUvArray(0, uvArray)
    mesh.clearAfterUpload = true

    local subMesh = Amaz.SubMesh()
    subMesh.primitive = Amaz.Primitive.TRIANGLES
    subMesh.indices16 = indices
    subMesh.mesh = mesh

    mesh:addSubMesh(subMesh)

    return mesh
end

--- init the script data (optional)
function Sprite2DModule:init()
end

--- seek per frame (optional)
function Sprite2DModule:seek()
end

--- reset the script data (optional)
function Sprite2DModule:reset()
    for i = 1, #self.sprite2DList do
        local se = self.sprite2DList[i]
        se:destroy()
    end
    self.sprite2DList = {}
	collectgarbage("collect")
end

return Sprite2DModule