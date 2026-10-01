#version 300 es
precision highp float;

in vec3 position;
in vec2 texcoord0;
out vec2 uv0;
out vec4 v_ScreenPos;
out float v_Seed;
uniform mat4 u_MVP;
void main() 
{ 
    //gl_Position = u_MVP * position;
    vec4 pos = vec4(position.xy, 0.0, 1.0);
    gl_Position = u_MVP * pos;
    uv0 = texcoord0;
    uv0.y = 1. - uv0.y;
    v_Seed = position.z;
    v_ScreenPos = gl_Position;
}
