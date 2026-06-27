<?php
/**
 * SEO Agent — Cocoon の SEO 用カスタムフィールドを REST API から更新できるようにする。
 *
 * 目的: エージェントが投稿時に「メタディスクリプション / メタキーワード / SEOタイトル」を
 *       自動入力できるようにする（Cocoon のフィールドは既定では REST 非公開のため登録する）。
 *
 * 設置方法（どちらか1つ）:
 *   A) mu-plugins に置く（推奨・確実）:
 *      wp-content/mu-plugins/ フォルダ（無ければ作成）に、このファイルを
 *      seo-agent-meta.php という名前でアップロードするだけ。自動で有効化される。
 *   B) コードスニペットプラグイン（WPCode / Code Snippets 等）に、<?php を除いた
 *      中身（add_action〜）を貼り付けて有効化。
 *
 * ※ 設置後、エージェントが入力したメタが Cocoon の SEO 欄に反映される。
 *    反映を確認するには、記事ページのソースで <meta name="description"> を見る。
 */

add_action('init', function () {
    $keys = array(
        'the_page_seo_title',        // Cocoon: SEOタイトル
        'the_page_meta_description', // Cocoon: メタディスクリプション
        'the_page_meta_keywords',    // Cocoon: メタキーワード
    );
    foreach ($keys as $key) {
        register_post_meta('post', $key, array(
            'type'          => 'string',
            'single'        => true,
            'show_in_rest'  => true,
            'auth_callback' => function () {
                return current_user_can('edit_posts');
            },
        ));
    }
});
