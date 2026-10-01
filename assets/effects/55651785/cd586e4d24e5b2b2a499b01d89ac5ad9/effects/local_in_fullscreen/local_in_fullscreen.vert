#version 300 es
precision highp float;

in vec3 position;
in vec2 texcoord0;

out vec2 v_local_uv;
out vec2 v_screen_uv;
out vec2 m;
out vec2 n;

uniform mat4 u_MVP;
uniform mat4 u_MV;
uniform mat4 u_Model;
uniform vec4 u_ScreenParams;
uniform mat4 u_InvModel;
uniform vec2 rect;

void main()
{
    v_local_uv = texcoord0 * 2.0 - 1.0;
    gl_Position = vec4(v_local_uv.xy, 0.0, 1.0);
    float y = (v_local_uv.y / position.y);
    float x = (v_local_uv.x / position.x);
    y = v_local_uv.y - position.y;
    x = v_local_uv.x - position.x;
    v_local_uv.x *= u_ScreenParams.x / u_ScreenParams.y;
    v_local_uv = (u_InvModel * vec4(v_local_uv, 0.0, 1.0)).xy;
    vec2 pos = vec2(position.x, (1. - (position.y * 0.5 + 0.5)) * 2.0 - 1.0);
    m = pos.xy;
    n = pos.xy * (texcoord0 * 2.0 - 1.0);
    v_screen_uv = texcoord0;
}
