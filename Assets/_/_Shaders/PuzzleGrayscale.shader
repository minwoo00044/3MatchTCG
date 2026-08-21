Shader "3MatchTCG/PuzzleGrayscale"
{
    Properties
    {
        [PerRendererData] _MainTex ("Sprite Texture", 2D) = "white" {}
        _Color ("Tint", Color) = (1,1,1,1)
        [PerRendererData] _GrayscaleAmount ("Grayscale", Range(0,1)) = 0
        [MaterialToggle] PixelSnap ("Pixel snap", Float) = 0
    }

    SubShader
    {
        Tags
        {
            "Queue"="Transparent"
            "IgnoreProjector"="True"
            "RenderType"="Transparent"
            "PreviewType"="Plane"
            "CanUseSpriteAtlas"="True"
        }

        Cull Off
        Lighting Off
        ZWrite Off
        Blend One OneMinusSrcAlpha

        Pass
        {
            CGPROGRAM
            #pragma vertex SpriteVert
            #pragma fragment GrayscaleFrag
            #pragma target 2.0
            #pragma multi_compile_instancing
            #pragma multi_compile_local _ PIXELSNAP_ON

            #include "UnitySprites.cginc"

            float _GrayscaleAmount;

            fixed4 GrayscaleFrag(v2f IN) : SV_Target
            {
                fixed4 color = SampleSpriteTexture(IN.texcoord) * IN.color;
                fixed luminance = dot(color.rgb, fixed3(0.299, 0.587, 0.114));
                color.rgb = lerp(color.rgb, luminance.xxx, saturate(_GrayscaleAmount));
                color.rgb *= color.a;
                return color;
            }
            ENDCG
        }
    }
}
