using Godot;
using System.Collections.Generic;

public partial class NpcController : CharacterBody2D
{
    [Export] public string NpcId { get; set; } = "";
    [Export] public string DisplayName { get; set; } = "NPC";

    private Label _label = null!;
    private Sprite2D _sprite = null!;
    private Area2D _interactionArea = null!;
    private Vector2 _targetPosition;
    private bool _isMoving = false;
    private float _moveSpeed = 100f;
    private bool _playerNearby = false;

    public override void _Ready()
    {
        _label = GetNode<Label>("Label3D");
        _sprite = GetNode<Sprite2D>("Sprite2D");
        _interactionArea = GetNode<Area2D>("InteractionArea");
        _label.Text = DisplayName;
        _targetPosition = GlobalPosition;

        LoadNpcSprite();

        _interactionArea.BodyEntered += OnInteractionAreaBodyEntered;
        _interactionArea.BodyExited += OnInteractionAreaBodyExited;
    }

    private void LoadNpcSprite()
    {
        if (string.IsNullOrWhiteSpace(NpcId))
            return;

        var path = $"res://assets/npcs/{NpcId}/sprite_idle.png";

        if (!ResourceLoader.Exists(path))
        {
            GD.PushWarning($"NPC sprite not found: {path}");
            return;
        }

        var texture = GD.Load<Texture2D>(path);

        if (_sprite != null)
            _sprite.Texture = texture;
    }

    public override void _Process(double delta)
    {
        if (!_isMoving)
            return;

        var distance = _targetPosition - GlobalPosition;
        if (distance.Length() < 2f)
        {
            GlobalPosition = _targetPosition;
            _isMoving = false;
            return;
        }

        var direction = distance.Normalized();
        GlobalPosition += direction * _moveSpeed * (float)delta;
    }

    public override void _UnhandledInput(InputEvent @event)
    {
        if (_playerNearby && @event.IsActionPressed("interact"))
        {
            EmitSignal(SignalName.NpcInteracted, NpcId);
            GetViewport().SetInputAsHandled();
        }
    }

    public void MoveTo(Vector2 target)
    {
        _targetPosition = target;
        _isMoving = true;
    }

    public void SetDisplayName(string name)
    {
        DisplayName = name;
        if (_label != null)
            _label.Text = name;
    }

    private void OnInteractionAreaBodyEntered(Node body)
    {
        if (body.IsInGroup("player"))
        {
            _playerNearby = true;
            GD.Print($"Player near NPC: {NpcId} ({DisplayName})");
        }
    }

    private void OnInteractionAreaBodyExited(Node body)
    {
        if (body.IsInGroup("player"))
        {
            _playerNearby = false;
        }
    }

    // Define the signal
    [Signal] public delegate void NpcInteractedEventHandler(string npcId);
}
