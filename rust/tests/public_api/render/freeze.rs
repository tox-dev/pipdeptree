use super::{execute, render_site, text};

#[test]
fn renders_freeze_forward_and_reverse() {
    let site = render_site();

    let forward = execute(&site, &["--freeze", "--depth", "1"]);
    let reverse = execute(&site, &["--freeze", "--reverse", "--depth", "1"]);

    assert_eq!(
        (text(&forward), text(&reverse)),
        (
            concat!(
                "graph==1\n",
                "other==1\n",
                "  child==1\n",
                "root==1\n",
                "  child==1\n",
                "  missing\n",
                "  unique==1\n",
            ),
            concat!(
                "child==1\n",
                "  other==1\n",
                "  root==1\n",
                "graph==1\n",
                "leaf==1\n",
                "  unique==1\n",
            ),
        )
    );
}
