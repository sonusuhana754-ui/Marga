import re
from sqlalchemy.orm import DeclarativeBase, declared_attr


class Base(DeclarativeBase):
    """
    SQLAlchemy 2.0 Declarative Base.
    All database models should inherit from this class.
    """

    @declared_attr.directive
    def __tablename__(cls) -> str:
        """
        Automatically generate lowercase snake_case table name from class name.
        Example: SampleModel -> sample_model
        """
        # Convert camelCase / PascalCase to snake_case
        pattern = re.compile(r'(?<!^)(?=[A-Z])')
        return pattern.sub('_', cls.__name__).lower()
