#version 300 es
precision highp float;

layout(location = 0) out vec4 FragColor;

in vec2 o_uv;
in float o_CurTextLine;

uniform sampler2D u_SeqTex1;
uniform sampler2D u_SeqTex2;
uniform sampler2D u_SeqTex3;
uniform sampler2D u_SeqTex4;
uniform sampler2D u_SeqTex5;
uniform sampler2D u_SeqTex6;
uniform sampler2D u_SeqTex7;
uniform sampler2D u_SeqTex8;
uniform sampler2D u_SeqTex9;

void main(void)
{
    vec2 uv0 = o_uv;
    vec4 res = vec4(o_uv, 0, 1);

    vec4 seqCol1 = texture(u_SeqTex1, uv0);
    vec4 seqCol2 = texture(u_SeqTex2, uv0);
    vec4 seqCol3 = texture(u_SeqTex3, uv0);
    vec4 seqCol4 = texture(u_SeqTex4, uv0);
    vec4 seqCol5 = texture(u_SeqTex5, uv0);
    vec4 seqCol6 = texture(u_SeqTex6, uv0);
    vec4 seqCol7 = texture(u_SeqTex7, uv0);
    vec4 seqCol8 = texture(u_SeqTex8, uv0);
    vec4 seqCol9 = texture(u_SeqTex9, uv0);

    if(o_CurTextLine < 1.5)
        res = texture(u_SeqTex1, uv0);

    else if(o_CurTextLine < 2.5)
        res = texture(u_SeqTex2, uv0);

    else if(o_CurTextLine < 3.5)
        res = texture(u_SeqTex3, uv0);

    else if(o_CurTextLine < 4.5)
        res = texture(u_SeqTex4, uv0);

    else if(o_CurTextLine < 5.5)
        res = texture(u_SeqTex5, uv0);

    else if(o_CurTextLine < 6.5)
        res = texture(u_SeqTex6, uv0);

    else if(o_CurTextLine < 7.5)
        res = texture(u_SeqTex7, uv0);
    
    else if(o_CurTextLine < 8.5)
        res = texture(u_SeqTex8, uv0);

    else if(o_CurTextLine < 9.5)
        res = texture(u_SeqTex9, uv0);
    // res = seqCol1;
    // res = mix(seqCol2, res, res.a);
    // res = mix(seqCol3, res, res.a);
    // res = mix(seqCol4, res, res.a);
    // res = vec4(o_uv, 0, 1);
    // res = vec4(0);
    FragColor = res;
}