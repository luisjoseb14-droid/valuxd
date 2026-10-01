attribute vec4 position;
attribute vec2 texcoord0;
varying vec2 uv0;
varying vec2 v_screenUV;
uniform mat4 u_MVP;
uniform vec4 u_ScreenParams;

void main()
{
    vec4 newPos = u_MVP * position;
    gl_Position = newPos;
    uv0 = texcoord0;
    uv0.y = 1.0 - uv0.y;
}
