# APSAL Semantic Field Reference / APSAL 语义字段参考

> Generated from the normative semantic registry. Do not edit by hand. / 由规范语义注册表生成，请勿手工编辑。

| Path | Role | English meaning | 中文含义 | Affects | Compile | QA |
|---|---|---|---|---|---|---|
| `shots.*.framing` | `camera` | Controls subject scale and visible world information. | 控制主体尺度以及本镜可见的世界信息量。 | `camera.subject_scale`<br>`world.visible_information`<br>`emotion.viewer_distance` | `camera` | `framing_matches_intent`<br>`required_action_remains_visible` |
| `shots.*.action` | `event` | Defines an observable event before pose and its world-state consequence. | 定义姿势之前可观察的事件及其世界状态后果。 | `event.state_transition`<br>`look.prop_state`<br>`sequence.continuity` | `event` | `action_is_physically_legible`<br>`action_changes_or_reveals_state` |
| `shots.*.hands` | `quality_control` | Defines hand visibility, ownership and physical participation in the action. | 定义手部可见性、道具归属及其对动作的物理参与。 | `subject.anatomy`<br>`event.legibility`<br>`look.prop_ownership` | `quality_control` | `hands_are_anatomically_plausible`<br>`hands_match_action` |
| `shots.*.gaze` | `emotion` | Defines motivated attention and its relation to event, space or another subject. | 定义有动机的注意方向，以及它与事件、空间或人物的关系。 | `emotion.external_expression`<br>`event.motivation`<br>`composition.attention` | `emotion` | `gaze_has_motivation`<br>`gaze_direction_is_spatially_coherent` |
| `shots.*.composition` | `camera` | Organizes subject, depth, foreground, background and negative space as a relation system. | 把主体、景深、前后景与留白组织为关系系统。 | `camera.viewpoint`<br>`world.geometry`<br>`content.emphasis` | `camera` | `composition_is_distinct`<br>`world_geometry_is_coherent` |
