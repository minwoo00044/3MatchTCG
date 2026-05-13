using UnityEngine;
using UnityEditor;
using System;
using System.IO;

public class SOBatchCreator : EditorWindow
{
    private DefaultAsset inputFolder;
    private DefaultAsset outputFolder;

    [MenuItem("Tools/SO Batch Creator")]
    public static void ShowWindow()
    {
        GetWindow<SOBatchCreator>("SO 생성기");
    }

    private void OnGUI()
    {
        GUILayout.Label("스크립트를 읽어 ScriptableObject를 일괄 생성합니다.", EditorStyles.boldLabel);
        EditorGUILayout.Space();

        inputFolder = (DefaultAsset)EditorGUILayout.ObjectField("입력 폴더 (Scripts)", inputFolder, typeof(DefaultAsset), false);
        outputFolder = (DefaultAsset)EditorGUILayout.ObjectField("출력 폴더 (Assets)", outputFolder, typeof(DefaultAsset), false);

        EditorGUILayout.Space();

        if (GUILayout.Button("SO 일괄 생성 실행", GUILayout.Height(30)))
        {
            CreateScriptsToSO();
        }
    }

    private void CreateScriptsToSO()
    {
        if (inputFolder == null || outputFolder == null)
        {
            EditorUtility.DisplayDialog("오류", "입력 및 출력 폴더를 모두 지정해주세요.", "확인");
            return;
        }

        string inputPath = AssetDatabase.GetAssetPath(inputFolder);
        string outputPath = AssetDatabase.GetAssetPath(outputFolder);

        // SearchOption.TopDirectoryOnly를 사용하여 하위 폴더 검사 제외
        string[] scriptFiles = Directory.GetFiles(inputPath, "*.cs", SearchOption.TopDirectoryOnly);
        int count = 0;

        foreach (string filePath in scriptFiles)
        {
            // 시스템 경로를 유니티 에셋 경로 형식(Assets/...)으로 변환
            string assetPath = filePath.Replace(Application.dataPath, "Assets").Replace("\\", "/");
            MonoScript script = AssetDatabase.LoadAssetAtPath<MonoScript>(assetPath);

            if (script != null)
            {
                Type scriptType = script.GetClass();

                if (scriptType != null && 
                    typeof(ScriptableObject).IsAssignableFrom(scriptType) && 
                    !scriptType.IsAbstract && 
                    !scriptType.IsGenericType)
                {
                    string finalAssetPath = $"{outputPath}/{scriptType.Name}.asset";

                    if (File.Exists(Path.GetFullPath(finalAssetPath)))
                    {
                        Debug.LogWarning($"{scriptType.Name} 에셋이 이미 존재하여 건너뜁니다.");
                        continue;
                    }

                    ScriptableObject soInstance = CreateInstance(scriptType);
                    AssetDatabase.CreateAsset(soInstance, finalAssetPath);
                    count++;
                }
            }
        }

        AssetDatabase.SaveAssets();
        AssetDatabase.Refresh();
        EditorUtility.DisplayDialog("완료", $"{count}개의 ScriptableObject가 생성되었습니다.", "확인");
    }
}