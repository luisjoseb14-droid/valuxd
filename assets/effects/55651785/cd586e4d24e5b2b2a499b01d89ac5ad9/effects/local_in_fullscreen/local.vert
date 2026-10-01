#version 300 es
precision highp float;

in vec3 position;
in vec2 texcoord0;

out vec2 o_uv;

uniform mat4 u_MVP;

void main()
{
    o_uv = texcoord0;
    o_uv.y = 1.-o_uv.y;
    gl_Position = u_MVP * vec4(position.xy, 0.0, 1.0);
}
