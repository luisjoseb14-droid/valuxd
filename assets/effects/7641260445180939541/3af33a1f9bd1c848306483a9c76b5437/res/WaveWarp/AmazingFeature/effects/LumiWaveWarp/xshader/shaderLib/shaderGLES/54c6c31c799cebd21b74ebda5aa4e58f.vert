
uniform vec4 u_ScreenParams;

attribute vec4 a_position;
varying vec2 v_p;
attribute vec2 a_texcoord0;

void main()
{
    gl_Position = a_position;
    v_p = vec2(a_texcoord0.x, 1.0 - a_texcoord0.y) * u_ScreenParams.xy;
}

