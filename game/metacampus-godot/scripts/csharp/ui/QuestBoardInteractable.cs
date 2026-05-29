using Godot;

public partial class QuestBoardInteractable : Area2D
{
    private Label _promptLabel = null!;
    private QuestBoardController _questBoard = null!;
    private bool _playerNearby = false;

    public override void _Ready()
    {
        _promptLabel = GetNode<Label>("PromptLabel");
        _questBoard = GetNode<QuestBoardController>("/root/Main/QuestBoard");
        _promptLabel.Visible = false;

        LoadSprite();

        BodyEntered += OnBodyEntered;
        BodyExited += OnBodyExited;
    }

    private void LoadSprite()
    {
        var spritePath = "res://assets/interactables/quest_board.png";
        if (ResourceLoader.Exists(spritePath))
        {
            var sprite = GetNode<Sprite2D>("Sprite2D");
            sprite.Texture = GD.Load<Texture2D>(spritePath);
        }
    }

    public override void _UnhandledInput(InputEvent @event)
    {
        if (_playerNearby && @event.IsActionPressed("interact"))
        {
            _questBoard.Visible = !_questBoard.Visible;
            GetViewport().SetInputAsHandled();
        }
    }

    private void OnBodyEntered(Node body)
    {
        if (body.IsInGroup("player"))
        {
            _playerNearby = true;
            _promptLabel.Visible = true;
        }
    }

    private void OnBodyExited(Node body)
    {
        if (body.IsInGroup("player"))
        {
            _playerNearby = false;
            _promptLabel.Visible = false;
        }
    }
}
