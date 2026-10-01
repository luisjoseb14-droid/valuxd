#version 300 es
precision highp float;

in vec3 position;
in vec2 texcoord0;

out vec2 o_uv;

void main()
{
    o_uv = texcoord0;
    o_uv.y = 1.-o_uv.y;
    gl_Position = vec4(sign(position.xy), 0.0, 1.0);
}
