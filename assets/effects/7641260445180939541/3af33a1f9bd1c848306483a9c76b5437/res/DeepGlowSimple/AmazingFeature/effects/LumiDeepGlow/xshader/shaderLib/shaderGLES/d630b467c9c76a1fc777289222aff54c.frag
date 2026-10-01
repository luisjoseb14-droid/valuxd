precision highp float;
precision highp int;

uniform mediump sampler2D u_inputTex;

varying vec2 v_uv;

void main()
{
    gl_FragData[0] = texture2D(u_inputTex, v_uv);
}

